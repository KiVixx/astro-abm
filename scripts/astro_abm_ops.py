#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.questdb.yml"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
OUTPUT_ROOT = ROOT / "astro_research" / "output"
ASTRO_DAILY_START = "1926-01-01"
ASTRO_DAILY_QUESTDB_START = "1970-01-01"
ASTRO_DAILY_END = "2025-12-31"
ASTRO_DAILY_SNAPSHOT = OUTPUT_ROOT / "parquet/astro_daily_1926_2025"

LOCAL_DATA_FILES = {
    "SPX": ROOT / "astro_research/data/local/equity/spx_daily.csv",
    "Gold": ROOT / "astro_research/data/local/commodities/gold_daily.csv",
    "DXY": ROOT / "astro_research/data/local/fx/dxy_daily.csv",
    "CreditProxy": ROOT / "astro_research/data/local/credit/hy_oas_daily.csv",
}

RESEARCH_INPUT_FILES = {
    "astro_daily_features": OUTPUT_ROOT / "parquet/astro_daily_1926_2025/astro_daily_features.csv",
    "astro_event_windows": OUTPUT_ROOT / "parquet/astro_daily_1926_2025/astro_event_windows.csv",
    "macro_core_aspect_chunks": OUTPUT_ROOT / "parquet/aspect_chunks_mvp35/macro_core_1926_2025/aspects",
    "market_daily_features": OUTPUT_ROOT / "parquet/market_daily/market_daily_features.parquet",
    "financial_stress_daily": OUTPUT_ROOT / "parquet/financial_stress/financial_stress_daily.parquet",
    "research_events": OUTPUT_ROOT / "parquet/research_events/research_events.parquet",
    "research_hypotheses": OUTPUT_ROOT / "parquet/research_hypotheses/research_hypotheses.parquet",
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-command Astro ABM database and data operations.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Print environment, Docker, database, local-data, and output readiness.")

    bootstrap = sub.add_parser("bootstrap", help="Create .env if missing, start QuestDB+maintenance, apply migrations, print status.")
    bootstrap.add_argument("--db-only", action="store_true", help="Start QuestDB only; do not start the maintenance daemon.")
    bootstrap.add_argument("--no-build", action="store_true", help="Do not rebuild the maintenance image.")
    bootstrap.add_argument("--skip-astro-daily", action="store_true", help="Skip the 100-year core daily astro dataset build/ingest.")
    bootstrap.add_argument("--timeout", type=int, default=90, help="Seconds to wait for QuestDB.")

    up = sub.add_parser("up", help="Start Docker services.")
    up.add_argument("--db-only", action="store_true", help="Start QuestDB only.")
    up.add_argument("--no-build", action="store_true", help="Do not build images.")

    sub.add_parser("down", help="Stop Docker services without deleting volumes.")

    migrate = sub.add_parser("migrate", help="Apply hourly and daily QuestDB schemas.")
    migrate.add_argument("--timeout", type=int, default=90, help="Seconds to wait for QuestDB.")

    maintain = sub.add_parser("maintain-now", help="Run one local hourly and daily maintenance pass.")
    maintain.add_argument("--hourly-only", action="store_true")
    maintain.add_argument("--daily-only", action="store_true")
    maintain.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success even if a transient upstream source fails; failed tasks remain visible in the summary.",
    )
    maintain.add_argument("--skip-astro-daily", action="store_true", help="Skip 100-year core daily astro dataset maintenance.")

    astro_daily = sub.add_parser("astro-daily", help="Ensure the 100-year core daily astro dataset snapshot and QuestDB tables exist.")
    astro_daily.add_argument("--force", action="store_true", help="Rebuild the snapshot and re-ingest even if QuestDB already looks complete.")
    astro_daily.add_argument("--skip-ingest", action="store_true", help="Only build/refresh the local snapshot; do not ingest QuestDB.")
    astro_daily.add_argument("--include-exact-aspects", action="store_true", help="Include expensive exact all-body aspect events in the core snapshot.")

    smoke = sub.add_parser("smoke", help="Run a small public smoke build that does not require private local CSVs.")
    smoke.add_argument("--start", default="2020-01-01")
    smoke.add_argument("--end", default="2020-01-07")

    checkpoint = sub.add_parser("checkpoint", help="Run the research workflow checkpoint.")
    checkpoint.add_argument("--check-only", action="store_true", help="Validate existing checkpoint outputs without regeneration.")

    args = parser.parse_args(argv)
    if args.command == "status":
        return command_status()
    if args.command == "bootstrap":
        ensure_env_file()
        command_up(db_only=True, build=False)
        wait_for_questdb(timeout=args.timeout)
        command_migrate(timeout=args.timeout)
        if not args.db_only:
            if not args.skip_astro_daily:
                command_ensure_astro_daily()
            command_up(db_only=False, build=not args.no_build)
        return command_status()
    if args.command == "up":
        return command_up(db_only=args.db_only, build=not args.no_build)
    if args.command == "down":
        return run(["docker", "compose", "-f", str(COMPOSE_FILE), "--profile", "maintenance", "down"]).returncode
    if args.command == "migrate":
        return command_migrate(timeout=args.timeout)
    if args.command == "maintain-now":
        return command_maintain_now(
            hourly=not args.daily_only,
            daily=not args.hourly_only,
            allow_partial=args.allow_partial,
            ensure_astro_daily=not args.hourly_only and not args.skip_astro_daily,
        )
    if args.command == "astro-daily":
        return command_ensure_astro_daily(
            force=args.force,
            ingest=not args.skip_ingest,
            include_exact_aspects=args.include_exact_aspects,
        )
    if args.command == "smoke":
        return command_smoke(start=args.start, end=args.end)
    if args.command == "checkpoint":
        return command_checkpoint(check_only=args.check_only)
    parser.error(f"Unhandled command: {args.command}")
    return 2


def command_up(*, db_only: bool, build: bool) -> int:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    if not db_only:
        cmd.extend(["--profile", "maintenance"])
    cmd.extend(["up", "-d"])
    if build and not db_only:
        cmd.append("--build")
    return run(cmd).returncode


def command_migrate(*, timeout: int) -> int:
    wait_for_questdb(timeout=timeout)
    statements = []
    for sql_file in sql_files():
        statements.extend((sql_file, statement) for statement in split_sql_statements(sql_file.read_text()))
    if not statements:
        print("No SQL statements found.")
        return 1

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("psycopg is required. Run `uv sync` first.") from exc

    env = read_env_file(ENV_FILE)
    connection = psycopg.connect(
        host=env.get("QUESTDB_HOST", os.getenv("QUESTDB_HOST", "localhost")),
        port=int(env.get("QUESTDB_PG_PORT", os.getenv("QUESTDB_PG_PORT", "8812"))),
        user=env.get("QUESTDB_USER", os.getenv("QUESTDB_USER", "admin")),
        password=env.get("QUESTDB_PASSWORD", os.getenv("QUESTDB_PASSWORD", "quest")),
        dbname=env.get("QUESTDB_DATABASE", os.getenv("QUESTDB_DATABASE", "qdb")),
        autocommit=True,
    )
    applied = 0
    with connection:
        with connection.cursor() as cursor:
            for sql_file, statement in statements:
                cursor.execute(statement)
                applied += 1
                print(f"applied {sql_file.relative_to(ROOT)}")
    print(f"migrations_applied={applied}")
    return 0


def command_status() -> int:
    checks: list[CheckResult] = []
    checks.append(CheckResult("git", True, git_summary()))
    checks.append(CheckResult("python", True, sys.version.split()[0]))
    checks.append(command_version("uv"))
    checks.append(command_version("docker"))
    checks.append(CheckResult(".env", ENV_FILE.exists(), "present" if ENV_FILE.exists() else "missing; bootstrap will copy .env.example"))
    checks.append(CheckResult("FRED_API_KEY", bool(env_value("FRED_API_KEY")), "present" if env_value("FRED_API_KEY") else "missing; FRED macro data will be skipped"))
    checks.extend(local_data_checks())
    checks.extend(research_input_checks())
    checks.append(CheckResult("questdb_tcp", tcp_open("localhost", int(env_value("QUESTDB_PG_PORT") or "8812")), "localhost:8812"))
    db_tables = questdb_table_summary()
    checks.append(CheckResult("questdb_tables", db_tables != "unavailable", db_tables))
    astro_daily_ready = astro_daily_snapshot_ready() and (astro_daily_questdb_ready() if db_tables != "unavailable" else False)
    checks.append(
        CheckResult(
            "astro_daily_100y_questdb",
            astro_daily_ready,
            "snapshot 1926-2025; QuestDB slice 1970-2025 complete"
            if astro_daily_ready
            else "missing or incomplete; run `make astro-daily`",
        )
    )

    print("# Astro ABM Ops Status")
    for check in checks:
        mark = "OK" if check.ok else "WARN"
        print(f"[{mark}] {check.name}: {check.detail}")
    print()
    run(["df", "-h", str(ROOT)], check=False)
    print()
    run(["docker", "system", "df"], check=False)
    return 0


def command_maintain_now(*, hourly: bool, daily: bool, allow_partial: bool = False, ensure_astro_daily: bool = True) -> int:
    code = 0
    if hourly:
        code |= run(["uv", "run", "astro-abm-maintain-hourly"], check=False).returncode
    if daily:
        code |= run(["uv", "run", "astro-abm-maintain-daily"], check=False).returncode
    if ensure_astro_daily:
        code |= command_ensure_astro_daily()
    if code and allow_partial:
        print("maintenance completed with partial upstream failures; see task summary above")
        return 0
    return code


def command_ensure_astro_daily(*, force: bool = False, ingest: bool = True, include_exact_aspects: bool = False) -> int:
    snapshot_ready = astro_daily_snapshot_ready()
    if ingest and not force and snapshot_ready and astro_daily_questdb_ready():
        print(f"astro daily QuestDB slice already complete: {ASTRO_DAILY_QUESTDB_START}..{ASTRO_DAILY_END}")
        return 0

    if force or not snapshot_ready:
        cmd = [
            "uv",
            "run",
            "python",
            "scripts/build_astro_daily.py",
            "--config",
            "astro_research/configs/astro_daily.yaml",
            "--start",
            ASTRO_DAILY_START,
            "--end",
            ASTRO_DAILY_END,
            "--write-parquet",
            str(ASTRO_DAILY_SNAPSHOT.relative_to(ROOT)),
            "--no-parquet",
            "--dry-run",
        ]
        if not include_exact_aspects:
            cmd.append("--skip-exact-aspects")
        code = run(cmd, check=False).returncode
        if code:
            return code
    else:
        print(f"astro daily snapshot already exists: {ASTRO_DAILY_SNAPSHOT.relative_to(ROOT)}")

    if not ingest:
        return 0

    code = run(
        [
            "uv",
            "run",
            "python",
            "scripts/ingest_astro_daily.py",
            "--parquet-dir",
            str(ASTRO_DAILY_SNAPSHOT.relative_to(ROOT)),
            "--skip-migrations",
            "--min-ts",
            ASTRO_DAILY_QUESTDB_START,
        ],
        check=False,
    ).returncode
    if code:
        return code
    return 0 if wait_for_astro_daily_questdb(timeout=30) else 1


def command_smoke(*, start: str, end: str) -> int:
    output = OUTPUT_ROOT / "smoke" / f"astro_daily_{start}_{end}"
    output.parent.mkdir(parents=True, exist_ok=True)
    code = run(
        [
            "uv",
            "run",
            "python",
            "scripts/build_astro_daily.py",
            "--config",
            "astro_research/configs/astro_daily.yaml",
            "--start",
            start,
            "--end",
            end,
            "--write-parquet",
            str(output.relative_to(ROOT)),
            "--dry-run",
        ]
    ).returncode
    if code:
        return code
    return run(["uv", "run", "python", "scripts/build_data_source_registry.py", "--config", "astro_research/configs/data_sources.yaml"]).returncode


def command_checkpoint(*, check_only: bool) -> int:
    cmd = ["uv", "run", "python", "scripts/research_workflow_checkpoint.py"]
    if check_only:
        cmd.append("--check-only")
    return run(cmd).returncode


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        print(".env already exists")
        return
    if not ENV_EXAMPLE.exists():
        print(".env.example missing; skipped .env creation")
        return
    shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
    print("created .env from .env.example")


def wait_for_questdb(*, timeout: int) -> None:
    host = env_value("QUESTDB_HOST") or "localhost"
    port = int(env_value("QUESTDB_PG_PORT") or "8812")
    deadline = time.time() + timeout
    last_error = "not attempted"
    while time.time() < deadline:
        ready, detail = questdb_ready(host=host, port=port)
        if ready:
            print(f"QuestDB ready at {host}:{port}")
            return
        last_error = detail
        time.sleep(1)
    raise SystemExit(f"QuestDB did not become ready at {host}:{port} within {timeout}s: {last_error}")


def questdb_ready(*, host: str, port: int) -> tuple[bool, str]:
    if not tcp_open(host, port):
        return False, "tcp not open"
    try:
        import psycopg
    except ImportError:
        return True, "tcp open; psycopg unavailable"
    env = read_env_file(ENV_FILE)
    try:
        with psycopg.connect(
            host=host,
            port=port,
            user=env.get("QUESTDB_USER", os.getenv("QUESTDB_USER", "admin")),
            password=env.get("QUESTDB_PASSWORD", os.getenv("QUESTDB_PASSWORD", "quest")),
            dbname=env.get("QUESTDB_DATABASE", os.getenv("QUESTDB_DATABASE", "qdb")),
            connect_timeout=1,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return True, "sql ready"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def sql_files() -> list[Path]:
    return [ROOT / "sql/schema_phase1.sql", *sorted((ROOT / "astro_research/migrations").glob("*.sql"))]


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    for char in sql:
        if char == "'":
            in_single = not in_single
        if char == ";" and not in_single:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def local_data_checks(root: Path = ROOT) -> list[CheckResult]:
    checks = []
    for label, path in LOCAL_DATA_FILES.items():
        target = root / path.relative_to(ROOT)
        checks.append(CheckResult(f"local_data_{label}", target.exists(), str(target.relative_to(root)) if target.exists() else "missing; local_full research will be incomplete"))
    return checks


def research_input_checks(root: Path = ROOT) -> list[CheckResult]:
    checks = []
    for label, path in RESEARCH_INPUT_FILES.items():
        target = root / path.relative_to(ROOT)
        checks.append(CheckResult(f"research_input_{label}", target.exists(), str(target.relative_to(root)) if target.exists() else "missing; run smoke/public rebuild first"))
    return checks


def astro_daily_snapshot_ready(root: Path = ROOT) -> bool:
    snapshot = root / ASTRO_DAILY_SNAPSHOT.relative_to(ROOT)
    required = (
        "astro_daily_positions.csv",
        "astro_retrograde_cycles.csv",
        "astro_moon_phase_events.csv",
        "astro_event_windows.csv",
        "astro_daily_features.csv",
        "astro_daily_facts.csv",
    )
    return all((snapshot / name).exists() and (snapshot / name).stat().st_size > 0 for name in required)


def astro_daily_questdb_ready(connection_factory=None, *, start: str = ASTRO_DAILY_QUESTDB_START, end: str = ASTRO_DAILY_END) -> bool:
    try:
        import psycopg
    except ImportError:
        return False

    expected_days = (_parse_date(end) - _parse_date(start)).days + 1
    connection_factory = connection_factory or _default_psycopg_connection
    try:
        with connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(), min(ts), max(ts) FROM astro_daily_features")
                count, min_ts, max_ts = cursor.fetchone()
        if min_ts is None or max_ts is None:
            return False
        min_date = _to_date(min_ts)
        max_date = _to_date(max_ts)
        return int(count) >= expected_days and min_date <= _parse_date(start) and max_date >= _parse_date(end)
    except (psycopg.Error, OSError, ValueError):
        return False


def wait_for_astro_daily_questdb(*, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if astro_daily_questdb_ready():
            return True
        time.sleep(1)
    return astro_daily_questdb_ready()


def _default_psycopg_connection():
    import psycopg

    env = read_env_file(ENV_FILE)
    return psycopg.connect(
        host=env.get("QUESTDB_HOST", os.getenv("QUESTDB_HOST", "localhost")),
        port=int(env.get("QUESTDB_PG_PORT", os.getenv("QUESTDB_PG_PORT", "8812"))),
        user=env.get("QUESTDB_USER", os.getenv("QUESTDB_USER", "admin")),
        password=env.get("QUESTDB_PASSWORD", os.getenv("QUESTDB_PASSWORD", "quest")),
        dbname=env.get("QUESTDB_DATABASE", os.getenv("QUESTDB_DATABASE", "qdb")),
        autocommit=True,
    )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env_value(name: str) -> str | None:
    return os.getenv(name) or read_env_file(ENV_FILE).get(name)


def tcp_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def questdb_table_summary() -> str:
    if not tcp_open("localhost", int(env_value("QUESTDB_PG_PORT") or "8812")):
        return "unavailable"
    try:
        import psycopg

        env = read_env_file(ENV_FILE)
        with psycopg.connect(
            host=env.get("QUESTDB_HOST", "localhost"),
            port=int(env.get("QUESTDB_PG_PORT", "8812")),
            user=env.get("QUESTDB_USER", "admin"),
            password=env.get("QUESTDB_PASSWORD", "quest"),
            dbname=env.get("QUESTDB_DATABASE", "qdb"),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count() FROM tables()")
                return f"{cursor.fetchone()[0]} tables"
    except Exception as exc:
        return f"unavailable ({type(exc).__name__}: {exc})"


def command_version(command: str) -> CheckResult:
    if not shutil.which(command):
        return CheckResult(command, False, "not found")
    completed = subprocess.run([command, "--version"], cwd=ROOT, capture_output=True, text=True)
    version = (completed.stdout or completed.stderr).splitlines()[0] if (completed.stdout or completed.stderr) else "found"
    return CheckResult(command, completed.returncode == 0, version)


def git_summary() -> str:
    completed = subprocess.run(["git", "status", "--short", "--branch"], cwd=ROOT, capture_output=True, text=True)
    return completed.stdout.strip().replace("\n", "; ")


def run(cmd: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("$ " + " ".join(str(part) for part in cmd), flush=True)
    return subprocess.run(list(cmd), cwd=ROOT, check=check)


if __name__ == "__main__":
    raise SystemExit(main())

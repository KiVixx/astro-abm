from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_ops_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "astro_abm_ops.py"
    spec = importlib.util.spec_from_file_location("astro_abm_ops", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_split_sql_statements_keeps_semicolon_inside_string():
    ops = load_ops_module()
    sql = "CREATE TABLE x (note VARCHAR); INSERT INTO x VALUES ('a;b');"

    statements = ops.split_sql_statements(sql)

    assert statements == ["CREATE TABLE x (note VARCHAR)", "INSERT INTO x VALUES ('a;b')"]


def test_read_env_file_ignores_comments_and_strips_quotes(tmp_path):
    ops = load_ops_module()
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
        # comment
        QUESTDB_HOST=localhost
        FRED_API_KEY="abc123"
        EMPTY=
        """.strip()
    )

    values = ops.read_env_file(env_path)

    assert values["QUESTDB_HOST"] == "localhost"
    assert values["FRED_API_KEY"] == "abc123"
    assert values["EMPTY"] == ""


def test_local_data_checks_report_missing_and_present_files(tmp_path):
    ops = load_ops_module()
    present = tmp_path / "astro_research/data/local/equity/spx_daily.csv"
    present.parent.mkdir(parents=True)
    present.write_text("date,close\n2020-01-01,100\n")

    checks = {check.name: check for check in ops.local_data_checks(root=tmp_path)}

    assert checks["local_data_SPX"].ok is True
    assert checks["local_data_Gold"].ok is False
    assert "missing" in checks["local_data_Gold"].detail


def test_research_input_checks_report_existing_directory(tmp_path):
    ops = load_ops_module()
    aspect_dir = tmp_path / "astro_research/output/parquet/aspect_chunks_mvp35/macro_core_1926_2025/aspects"
    aspect_dir.mkdir(parents=True)

    checks = {check.name: check for check in ops.research_input_checks(root=tmp_path)}

    assert checks["research_input_macro_core_aspect_chunks"].ok is True
    assert checks["research_input_research_events"].ok is False


def test_questdb_ready_uses_tcp_fallback_when_psycopg_missing(monkeypatch):
    ops = load_ops_module()
    monkeypatch.setattr(ops, "tcp_open", lambda host, port: True)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "psycopg":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    ready, detail = ops.questdb_ready(host="localhost", port=8812)

    assert ready is True
    assert detail == "tcp open; psycopg unavailable"


def test_maintain_now_allow_partial_returns_success(monkeypatch, capsys):
    ops = load_ops_module()

    class Result:
        def __init__(self, returncode: int):
            self.returncode = returncode

    calls: list[list[str]] = []

    def fake_run(cmd, *, check=True):
        calls.append(list(cmd))
        return Result(1 if cmd[-1] == "astro-abm-maintain-daily" else 0)

    monkeypatch.setattr(ops, "run", fake_run)

    strict_code = ops.command_maintain_now(hourly=True, daily=True, allow_partial=False, ensure_astro_daily=False)
    partial_code = ops.command_maintain_now(hourly=True, daily=True, allow_partial=True, ensure_astro_daily=False)

    assert strict_code == 1
    assert partial_code == 0
    assert calls.count(["uv", "run", "astro-abm-maintain-hourly"]) == 2
    assert calls.count(["uv", "run", "astro-abm-maintain-daily"]) == 2
    assert "partial upstream failures" in capsys.readouterr().out


def test_astro_daily_snapshot_ready_requires_core_csvs(tmp_path):
    ops = load_ops_module()
    snapshot = tmp_path / "astro_research/output/parquet/astro_daily_1926_2025"
    snapshot.mkdir(parents=True)

    assert ops.astro_daily_snapshot_ready(root=tmp_path) is False

    for name in (
        "astro_daily_positions.csv",
        "astro_retrograde_cycles.csv",
        "astro_moon_phase_events.csv",
        "astro_event_windows.csv",
        "astro_daily_features.csv",
        "astro_daily_facts.csv",
    ):
        (snapshot / name).write_text("header\n")

    assert ops.astro_daily_snapshot_ready(root=tmp_path) is True


def test_command_ensure_astro_daily_builds_snapshot_then_ingests(monkeypatch):
    ops = load_ops_module()

    class Result:
        returncode = 0

    calls: list[list[str]] = []

    def fake_run(cmd, *, check=True):
        calls.append(list(cmd))
        return Result()

    monkeypatch.setattr(ops, "astro_daily_questdb_ready", lambda: True)
    monkeypatch.setattr(ops, "astro_daily_snapshot_ready", lambda: False)
    monkeypatch.setattr(ops, "run", fake_run)

    code = ops.command_ensure_astro_daily()

    assert code == 0
    assert any("scripts/build_astro_daily.py" in call for call in calls)
    assert any("--skip-exact-aspects" in call for call in calls)
    assert any("scripts/ingest_astro_daily.py" in call for call in calls)


def test_command_research_prepare_builds_selectable_mode_command(monkeypatch):
    ops = load_ops_module()

    class Result:
        returncode = 0

    calls: list[list[str]] = []

    def fake_run(cmd, *, check=True):
        calls.append(list(cmd))
        return Result()

    monkeypatch.setattr(ops, "run", fake_run)

    code = ops.command_research_prepare(
        mode="formal",
        start="1926-01-01",
        end="2025-12-31",
        aspect_profile="macro_core",
        workers=4,
        ingest=True,
        run_batch=True,
        dry_run=False,
        strict_local_data=True,
    )

    assert code == 0
    command = calls[0]
    assert command[:4] == ["uv", "run", "python", "scripts/research_prepare.py"]
    assert command[command.index("--mode") + 1] == "formal"
    assert command[command.index("--workers") + 1] == "4"
    assert "--ingest" in command
    assert "--run-batch" in command
    assert "--strict-local-data" in command


def test_command_fetch_local_data_builds_safe_fetch_command(monkeypatch):
    ops = load_ops_module()

    class Result:
        returncode = 0

    calls: list[list[str]] = []

    def fake_run(cmd, *, check=True):
        calls.append(list(cmd))
        return Result()

    monkeypatch.setattr(ops, "run", fake_run)

    code = ops.command_fetch_local_data(
        assets=("SPX", "Gold"),
        all_assets=False,
        start="1926-01-01",
        end="2025-12-31",
        fred_api_key_env="FRED_API_KEY",
        dry_run=True,
        accept_terms=True,
    )

    assert code == 0
    command = calls[0]
    assert command[:4] == ["uv", "run", "python", "scripts/fetch_local_research_data.py"]
    assert command.count("--asset") == 2
    assert "SPX" in command
    assert "Gold" in command
    assert "--dry-run" in command
    assert "--accept-research-local-terms" in command

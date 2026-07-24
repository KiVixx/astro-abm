from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Sequence

from astro_abm.etl.maintenance import MaintenanceSummary, format_maintenance_summary
from astro_abm.etl.pipeline import normalize_to_utc_hour


DEFAULT_START = "1926-01-01"


@dataclass(frozen=True)
class ProductSnapshotTaskSummary:
    written: int = 0
    skipped_existing: int = 0
    errors: tuple[str, ...] = ()
    mode: str = ""
    steps_seen: int = 0
    warnings_seen: int = 0
    report_json_path: str = ""


@dataclass(frozen=True)
class CustomMarketSeriesTaskSummary:
    written: int = 0
    skipped_existing: int = 0
    errors: tuple[str, ...] = ()
    fetched: int = 0
    mode: str = "custom-market-series"


def run_product_snapshot_maintenance(
    *,
    run_ts: datetime | None = None,
    mode: str = "local-full",
    start: str = DEFAULT_START,
    end: str | None = None,
    fetch_local_data: bool = False,
    accept_research_local_terms: bool = False,
    ingest: bool = False,
    root: str | Path | None = None,
) -> MaintenanceSummary:
    """Refresh Parquet snapshots used by the scenario product layer.

    This task is intentionally read/build oriented: it refreshes ignored local
    research outputs under astro_research/output, and optionally ingests the
    rebuilt market/stress tables into QuestDB. It does not mutate source tables.
    """

    bucket_ts = normalize_to_utc_hour(run_ts or datetime.now(UTC))
    end = end or date.today().isoformat()
    root_path = _repo_root(root)

    tasks = []
    if fetch_local_data:
        tasks.append(("product_local_data_refresh", lambda: _fetch_local_data(root_path, start=start, end=end, accept_terms=accept_research_local_terms)))
    tasks.append(
        (
            "custom_market_series_refresh",
            lambda: _refresh_custom_market_series(end=end),
        )
    )
    tasks.append(("product_research_prepare", lambda: _research_prepare(root_path, mode=mode, start=start, end=end, ingest=ingest)))

    from astro_abm.etl.maintenance import run_maintenance_tasks

    return MaintenanceSummary(
        run_ts=bucket_ts,
        window_start=_parse_date_as_utc(start),
        window_end=_parse_date_as_utc(end),
        tasks=run_maintenance_tasks(tasks),
    )


def _fetch_local_data(root: Path, *, start: str, end: str, accept_terms: bool) -> ProductSnapshotTaskSummary:
    if not accept_terms:
        return ProductSnapshotTaskSummary(
            errors=("local data refresh requested but ASTRO_ABM_ACCEPT_RESEARCH_LOCAL_TERMS is not enabled",),
            mode="fetch-local-data",
        )
    command = [
        sys.executable,
        "scripts/fetch_local_research_data.py",
        "--all",
        "--start",
        start,
        "--end",
        end,
        "--provenance-mode",
        "local",
        "--accept-research-local-terms",
    ]
    completed = subprocess.run(command, cwd=root, check=False)
    return ProductSnapshotTaskSummary(
        errors=() if completed.returncode == 0 else (f"fetch-local-data failed: returncode={completed.returncode}",),
        mode="fetch-local-data",
    )


def _research_prepare(root: Path, *, mode: str, start: str, end: str, ingest: bool) -> ProductSnapshotTaskSummary:
    _ensure_research_path(root)
    from research.prepare import prepare_research

    result = prepare_research(
        root=root,
        mode=mode,
        start=start,
        end=end,
        ingest=ingest,
        run_batch=False,
        runner=lambda command: _run_python_command(root, command),
    )
    errors = () if result.status != "failed" else (f"research-prepare failed: {result.report_json_path}",)
    return ProductSnapshotTaskSummary(
        errors=errors,
        mode=mode,
        steps_seen=len(result.steps),
        warnings_seen=len(result.warnings),
        report_json_path=str(result.report_json_path),
    )


def _refresh_custom_market_series(*, end: str) -> CustomMarketSeriesTaskSummary:
    from astro_abm.market_series import run_custom_market_series_maintenance

    results = run_custom_market_series_maintenance(end=date.fromisoformat(end))
    errors = tuple(
        f"{result.series_id}: {error}"
        for result in results
        if result.status != "active"
        for error in result.errors
    )
    return CustomMarketSeriesTaskSummary(
        written=sum(result.rows_written for result in results if result.status == "active"),
        skipped_existing=sum(1 for result in results if result.fetched_rows == 0),
        errors=errors,
        fetched=sum(result.fetched_rows for result in results),
    )


def _run_python_command(root: Path, command: Sequence[str]) -> subprocess.CompletedProcess:
    translated = list(command)
    if translated[:3] == ["uv", "run", "python"]:
        translated = [sys.executable, *translated[3:]]
    elif translated[:2] == ["uv", "run"]:
        translated = [*translated[2:]]
    return subprocess.run(translated, cwd=root, check=False)


def _repo_root(root: str | Path | None) -> Path:
    if root:
        return Path(root).resolve()
    if os.getenv("ASTRO_ABM_REPO_ROOT"):
        return Path(os.environ["ASTRO_ABM_REPO_ROOT"]).resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "pyproject.toml").exists():
        return cwd
    return Path(__file__).resolve().parents[3]


def _ensure_research_path(root: Path) -> None:
    research_src = root / "astro_research" / "src"
    if research_src.exists() and str(research_src) not in sys.path:
        sys.path.insert(0, str(research_src))


def _parse_date_as_utc(value: str) -> datetime:
    return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=UTC)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh product-layer daily research snapshots.")
    parser.add_argument("--mode", choices=("public", "local-full", "formal"), default=os.getenv("ASTRO_ABM_PRODUCT_SNAPSHOT_MODE", "local-full"))
    parser.add_argument("--start", default=os.getenv("ASTRO_ABM_PRODUCT_SNAPSHOT_START", DEFAULT_START))
    parser.add_argument("--end", default=os.getenv("ASTRO_ABM_PRODUCT_SNAPSHOT_END"))
    parser.add_argument("--fetch-local-data", action="store_true", default=_env_bool("ASTRO_ABM_REFRESH_LOCAL_DATA"))
    parser.add_argument(
        "--accept-research-local-terms",
        action="store_true",
        default=_env_bool("ASTRO_ABM_ACCEPT_RESEARCH_LOCAL_TERMS"),
    )
    parser.add_argument("--ingest", action="store_true", default=_env_bool("ASTRO_ABM_PRODUCT_SNAPSHOT_INGEST"))
    args = parser.parse_args(argv)

    summary = run_product_snapshot_maintenance(
        mode=args.mode,
        start=args.start,
        end=args.end,
        fetch_local_data=args.fetch_local_data,
        accept_research_local_terms=args.accept_research_local_terms,
        ingest=args.ingest,
    )
    print(format_maintenance_summary(summary, title="Product Snapshot Maintenance Summary"))
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

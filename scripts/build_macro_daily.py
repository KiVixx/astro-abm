#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.calendar import parse_date
from astro_daily.config import _parse_simple_yaml
from astro_daily.ingest_questdb import apply_migrations, ingest_csv_snapshot
from research.coverage import build_series_coverage, expected_range, normalize_frequency, write_coverage_report
from research.macro_daily import build_macro_daily, export_macro_daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Build macro daily observations.")
    parser.add_argument("--config", default="astro_research/configs/macro_series.yaml")
    parser.add_argument("--start", default="1926-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--write-parquet", default="astro_research/output/parquet/macro_daily")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    result = build_macro_daily(ROOT / args.config, start=parse_date(args.start), end=parse_date(args.end))
    paths = export_macro_daily(result, ROOT / args.write_parquet)
    coverage = build_series_coverage(result.observations, data_version=result.data_version)
    coverage = _append_unavailable_series_coverage(
        coverage,
        diagnostics=result.diagnostics,
        config_path=ROOT / args.config,
        data_version=result.data_version,
    )
    coverage.to_csv(ROOT / args.write_parquet / "macro_series_coverage.csv", index=False)
    coverage.to_parquet(ROOT / args.write_parquet / "macro_series_coverage.parquet", index=False)
    write_coverage_report(coverage, ROOT / "astro_research/output/reports/macro_data_coverage.md")
    for warning in result.warnings:
        print(f"warning={warning}")
    if args.ingest:
        apply_migrations()
        counts = ingest_csv_snapshot(ROOT / args.write_parquet, tables=("macro_daily_observations",))
        print(f"ingested={counts}")
    zero_rows = int((result.diagnostics.get("row_count", pd.Series(dtype=int)) == 0).sum()) if not result.diagnostics.empty else 0
    print(f"rows={len(result.observations)} diagnostics={len(result.diagnostics)} zero_row_series={zero_rows} output={paths['parquet']}")
    return 0


def _append_unavailable_series_coverage(coverage: pd.DataFrame, *, diagnostics: pd.DataFrame, config_path: Path, data_version: str) -> pd.DataFrame:
    if diagnostics.empty or "row_count" not in diagnostics.columns:
        return coverage
    raw = _parse_simple_yaml(config_path.read_text())
    existing = set(coverage["asset"]) if "asset" in coverage.columns else set()
    rows = []
    for diagnostic in diagnostics.itertuples(index=False):
        if int(getattr(diagnostic, "row_count", 0)) != 0 or diagnostic.series_id in existing:
            continue
        series_config = raw.get("series", {}).get(diagnostic.series_id, {})
        frequency = normalize_frequency(str(series_config.get("original_frequency", "daily")))
        start = pd.Timestamp(diagnostic.observation_start, tz="UTC")
        end = pd.Timestamp(diagnostic.observation_end, tz="UTC")
        calendar_expected = pd.date_range(start, end, freq="D", tz="UTC")
        adjusted_expected = expected_range(start, end, frequency)
        rows.append(
            {
                "ts": pd.Timestamp.now(tz="UTC"),
                "asset": diagnostic.series_id,
                "source": diagnostic.source,
                "coverage_start_ts": start,
                "coverage_end_ts": end,
                "observation_count": 0,
                "missing_count": len(adjusted_expected),
                "missing_pct": 1.0 if len(adjusted_expected) else 0.0,
                "calendar_expected_count": len(calendar_expected),
                "calendar_missing_count": len(calendar_expected),
                "frequency_adjusted_expected_count": len(adjusted_expected),
                "frequency_adjusted_missing_count": len(adjusted_expected),
                "frequency_adjusted_missing_pct": 1.0 if len(adjusted_expected) else 0.0,
                "first_valid_ts": pd.NaT,
                "last_valid_ts": pd.NaT,
                "frequency": frequency,
                "data_version": data_version,
                "source_note": f"unavailable:{getattr(diagnostic, 'error_message', '')}",
            }
        )
    if not rows:
        return coverage
    return pd.concat([coverage, pd.DataFrame(rows)], ignore_index=True)


if __name__ == "__main__":
    raise SystemExit(main())

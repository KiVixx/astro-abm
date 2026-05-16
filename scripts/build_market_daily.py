#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.calendar import parse_date
from astro_daily.ingest_questdb import apply_migrations
from market_daily.build import build_market_daily_dataset, export_market_dataset
from market_daily.config import load_market_daily_config
from market_daily.ingest_questdb import ingest_market_frames
from research.coverage import build_asset_coverage, write_coverage_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build market daily bars/features.")
    parser.add_argument("--config", default="astro_research/configs/market_assets.yaml")
    parser.add_argument("--asset", action="append", default=None, help="Asset name. Can be repeated.")
    parser.add_argument("--source", default=None, help="Provider source filter, e.g. local_csv/fred/yfinance.")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--write-parquet", default="astro_research/output/parquet/market_daily")
    parser.add_argument("--no-parquet", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build/export only; do not ingest.")
    parser.add_argument("--ingest", action="store_true", help="Apply migrations and ingest into QuestDB.")
    args = parser.parse_args()

    config = load_market_daily_config(ROOT / args.config)
    bars, features = build_market_daily_dataset(
        config,
        root=ROOT,
        assets=tuple(args.asset) if args.asset else None,
        source=args.source,
        start=parse_date(args.start) if args.start else None,
        end=parse_date(args.end) if args.end else None,
    )
    paths = export_market_dataset(bars, features, ROOT / args.write_parquet, write_parquet=not args.no_parquet)
    coverage = build_asset_coverage(bars, data_version=config.data_version) if not bars.empty else build_asset_coverage(bars, data_version=config.data_version)
    coverage.to_csv(ROOT / args.write_parquet / "market_asset_coverage.csv", index=False)
    if not args.no_parquet:
        coverage.to_parquet(ROOT / args.write_parquet / "market_asset_coverage.parquet", index=False)
    write_coverage_report(coverage, ROOT / "astro_research/output/reports/market_data_coverage.md")
    warnings = bars.attrs.get("warnings", []) or features.attrs.get("warnings", [])
    print("Market daily build complete")
    print(f"assets={sorted(bars['asset'].unique().tolist()) if not bars.empty and 'asset' in bars.columns else []}")
    print(f"bars={len(bars)} features={len(features)} output_dir={ROOT / args.write_parquet}")
    print(f"coverage_rows={len(coverage)}")
    for warning in warnings:
        print(f"warning={warning}")
    print(f"files={len(paths)}")
    if args.ingest and not args.dry_run:
        apply_migrations()
        counts = ingest_market_frames(bars=bars, features=features)
        from astro_daily.ingest_questdb import ingest_csv_snapshot

        counts.update(ingest_csv_snapshot(ROOT / args.write_parquet, tables=("market_asset_coverage",)))
        print(f"ingested={counts}")
    else:
        print(f"ingest_skipped={not args.ingest or args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.ingest_questdb import apply_migrations, ingest_csv_snapshot
from research.source_registry import build_source_registry, write_source_registry_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MVP5 data source registry.")
    parser.add_argument("--config", default="astro_research/configs/data_sources.yaml")
    parser.add_argument("--write-parquet", default="astro_research/output/parquet/source_registry")
    parser.add_argument("--output", default="astro_research/output/reports/source_registry.md")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    registry = build_source_registry(ROOT / args.config, root=ROOT)
    output_dir = ROOT / args.write_parquet
    output_dir.mkdir(parents=True, exist_ok=True)
    registry.rows.to_csv(output_dir / "data_source_registry.csv", index=False)
    registry.rows.to_parquet(output_dir / "data_source_registry.parquet", index=False)
    report = write_source_registry_report(registry, ROOT / args.output)
    if args.ingest:
        apply_migrations()
        counts = ingest_csv_snapshot(output_dir, tables=("data_source_registry",))
        print(f"ingested={counts}")
    print(f"rows={len(registry.rows)} report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

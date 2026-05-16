#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.ingest_questdb import apply_migrations, ingest_csv_snapshot
from research.stress_features import build_financial_stress, export_financial_stress


def main() -> int:
    parser = argparse.ArgumentParser(description="Build financial stress daily features.")
    parser.add_argument("--config", default="astro_research/configs/financial_stress.yaml")
    parser.add_argument("--write-parquet", default="astro_research/output/parquet/financial_stress")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    result = build_financial_stress(ROOT / args.config, root=ROOT)
    paths = export_financial_stress(result, ROOT / args.write_parquet)
    for warning in result.warnings:
        print(f"warning={warning}")
    if args.ingest:
        apply_migrations()
        counts = ingest_csv_snapshot(ROOT / args.write_parquet, tables=("financial_stress_daily",))
        print(f"ingested={counts}")
    print(f"rows={len(result.frame)} output={paths['parquet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

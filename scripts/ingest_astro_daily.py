#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.ingest_questdb import apply_migrations, ingest_csv_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a daily astro research CSV snapshot into QuestDB.")
    parser.add_argument("--config", default="astro_research/configs/astro_daily.yaml", help="Reserved for parity with build script.")
    parser.add_argument("--parquet-dir", default="astro_research/output/parquet/astro_daily", help="Snapshot directory containing CSV files.")
    parser.add_argument("--questdb-dsn", default=None, help="Reserved; current implementation uses repo .env QuestDB settings.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    args = parser.parse_args()

    snapshot_dir = ROOT / args.parquet_dir
    if args.dry_run:
        print(f"Dry run: would ingest CSV snapshot from {snapshot_dir}")
        for path in sorted(snapshot_dir.glob("astro_*.csv")):
            print(f"- {path.name}")
        return 0
    if not args.skip_migrations:
        apply_migrations()
    counts = ingest_csv_snapshot(snapshot_dir)
    print("Astro daily ingest complete")
    for table, count in counts.items():
        print(f"{table}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

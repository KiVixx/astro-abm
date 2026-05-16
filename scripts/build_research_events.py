#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.ingest_questdb import apply_migrations, ingest_csv_snapshot
from research.research_events import build_research_events, export_research_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize astro sources into research_events.")
    parser.add_argument("--config", default="astro_research/configs/research_events.yaml")
    parser.add_argument("--write-parquet", default="astro_research/output/parquet/research_events")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    result = build_research_events(ROOT / args.config, root=ROOT)
    paths = export_research_events(result, ROOT / args.write_parquet)
    for warning in result.warnings:
        print(f"warning={warning}")
    if args.ingest:
        apply_migrations()
        counts = ingest_csv_snapshot(ROOT / args.write_parquet, tables=("research_events",))
        print(f"ingested={counts}")
    print(f"rows={len(result.events)} output={paths['parquet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.ingest_questdb import apply_migrations, ingest_csv_snapshot
from research.hypotheses import export_hypotheses, register_hypotheses


def main() -> int:
    parser = argparse.ArgumentParser(description="Register formal research hypotheses.")
    parser.add_argument("--config", default="astro_research/configs/research_hypotheses.yaml")
    parser.add_argument("--git-commit", default="auto")
    parser.add_argument("--write-parquet", default="astro_research/output/parquet/research_hypotheses")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    registry = register_hypotheses(ROOT / args.config, git_commit=args.git_commit)
    paths = export_hypotheses(registry, ROOT / args.write_parquet)
    if args.ingest:
        apply_migrations()
        counts = ingest_csv_snapshot(ROOT / args.write_parquet, tables=("research_hypotheses",))
        print(f"ingested={counts}")
    print(f"rows={len(registry.rows)} config_hash={registry.config_hash} output={paths['parquet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

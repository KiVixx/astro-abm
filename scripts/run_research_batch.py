#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.ingest_questdb import apply_migrations, ingest_csv_snapshot
from research.event_study_v2 import run_research_batch, write_batch_report
from research.io import read_table


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MVP5 formal research batch.")
    parser.add_argument("--config", default="astro_research/configs/research_batch_v1.yaml")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output", default="astro_research/output/reports/research_batch_v1")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    config_path = ROOT / args.config
    batch = run_research_batch(config_path, root=ROOT, run_id_override=args.run_id)
    hypothesis_path = ROOT / "astro_research/output/parquet/research_hypotheses/research_hypotheses.parquet"
    hypothesis_snapshot = read_table(hypothesis_path) if hypothesis_path.exists() else read_table(ROOT / "astro_research/output/parquet/research_hypotheses/research_hypotheses.csv")
    paths = write_batch_report(batch, ROOT / args.output, config_text=config_path.read_text(), hypothesis_snapshot=hypothesis_snapshot)
    if args.ingest:
        ingest_dir = ROOT / args.output
        batch.results.drop(columns=["multiple_testing_group"], errors="ignore").to_csv(ingest_dir / "event_study_results_v2.csv", index=False)
        batch.runs.to_csv(ingest_dir / "event_study_runs.csv", index=False)
        apply_migrations()
        counts = ingest_csv_snapshot(ingest_dir, tables=("event_study_runs", "event_study_results_v2"))
        print(f"ingested={counts}")
    print(f"run_id={batch.run_id} rows={len(batch.results)} output={paths['summary.md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

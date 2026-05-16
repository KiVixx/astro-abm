#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.ingest_questdb import apply_migrations
from research.config import load_event_study_config
from research.event_study import run_event_study
from research.ingest_questdb import ingest_event_study_results
from research.reports import write_event_study_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run astro event study v1.")
    parser.add_argument("--config", default="astro_research/configs/event_study_v1.yaml")
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ingest", action="store_true", help="Apply migrations and ingest results into QuestDB.")
    args = parser.parse_args()

    config_path = ROOT / args.config
    config = load_event_study_config(config_path)
    output_dir = ROOT / (args.output or f"astro_research/output/reports/{config.run_id}")
    study = run_event_study(config, root=ROOT)
    if args.dry_run:
        print("Event study dry run complete")
        print(f"rows={len(study.results)} output_skipped=true")
        return 0
    paths = write_event_study_report(
        results=study.results,
        config=config,
        output_dir=output_dir,
        config_text=config_path.read_text(),
    )
    print("Event study complete")
    print(f"run_id={config.run_id} rows={len(study.results)} output_dir={output_dir}")
    print(f"files={len(paths)}")
    if args.ingest:
        apply_migrations()
        count = ingest_event_study_results(study.results)
        print(f"ingested_event_study_results={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

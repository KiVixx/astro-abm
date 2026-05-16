#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.calendar import parse_date
from astro_daily.aspect_chunks import aspect_tasks, validate_aspect_chunks
from astro_daily.aspect_profiles import ASPECT_PROFILES, resolve_aspect_pairs
from astro_daily.config import load_astro_daily_config
from astro_daily.validate import validate_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the daily astro research snapshot.")
    parser.add_argument("--config", default="astro_research/configs/astro_daily.yaml")
    parser.add_argument("--snapshot-dir", default="astro_research/output/parquet/astro_daily")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--questdb-dsn", default=None, help="Reserved for future QuestDB validation.")
    parser.add_argument("--output", default="astro_research/output/reports/astro_daily_validation.md")
    parser.add_argument("--aspect-chunks-dir", default=None)
    parser.add_argument("--aspect-only", action="store_true")
    parser.add_argument("--aspect-profile", choices=tuple(ASPECT_PROFILES), default=None)
    parser.add_argument("--aspect-bodies", default=None)
    parser.add_argument("--aspect-pairs", default=None)
    parser.add_argument("--include-moon-aspects", choices=("true", "false"), default="false")
    args = parser.parse_args()

    config = load_astro_daily_config(ROOT / args.config)
    start = parse_date(args.start) if args.start else config.dataset.target_start
    end = parse_date(args.end) if args.end else config.dataset.target_end
    report = "" if args.aspect_only else validate_snapshot(ROOT / args.snapshot_dir, start=start, end=end, dataset_id=config.dataset.dataset_id)
    if args.aspect_chunks_dir:
        pairs = resolve_aspect_pairs(
            profile=args.aspect_profile,
            aspect_bodies=args.aspect_bodies,
            aspect_pairs=args.aspect_pairs,
            include_moon_aspects=args.include_moon_aspects == "true" or args.aspect_profile in {"all", "lunar_short_term"},
        )
        tasks = aspect_tasks(pairs=pairs, start=start, end=end)
        warnings = validate_aspect_chunks(
            output_dir=ROOT / args.aspect_chunks_dir,
            tasks=tasks,
            expected_min_ts=datetime(start.year, start.month, start.day, tzinfo=UTC),
            expected_max_ts=datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC),
        )
        report += "# Aspect Chunk Validation\n\n" if not report else "\n# Aspect Chunk Validation\n\n"
        report += f"Pairs: {len(pairs)}\n\nTasks: {len(tasks)}\n\n"
        report += "## Warnings\n"
        report += "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
        report += "\n"
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(report)
    print(f"Output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

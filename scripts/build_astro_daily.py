#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.build import build_astro_daily_dataset, export_dataset, validate_dataset
from astro_daily.calendar import parse_date
from astro_daily.config import load_astro_daily_config
from astro_daily.aspect_chunks import aspect_tasks, build_aspect_chunks, validate_aspect_chunks
from astro_daily.aspect_profiles import ASPECT_PROFILES, resolve_aspect_pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the daily astro research dataset snapshot.")
    parser.add_argument("--config", default="astro_research/configs/astro_daily.yaml")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--write-parquet", default="astro_research/output/parquet/astro_daily")
    parser.add_argument("--no-parquet", action="store_true", help="Only write CSV files.")
    parser.add_argument("--dry-run", action="store_true", help="Build and validate, but do not ingest QuestDB.")
    parser.add_argument("--aspect-profile", choices=tuple(ASPECT_PROFILES), default=None)
    parser.add_argument("--aspect-bodies", default=None, help="Comma-separated bodies for optimized aspect-only builds.")
    parser.add_argument("--aspect-pairs", default=None, help="Comma-separated pairs, e.g. Mars-Saturn,Jupiter/Saturn.")
    parser.add_argument("--include-moon-aspects", choices=("true", "false"), default="false")
    parser.add_argument("--aspect-start", default=None)
    parser.add_argument("--aspect-end", default=None)
    parser.add_argument("--aspect-year", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    config = load_astro_daily_config(ROOT / args.config)
    start = parse_date(args.start) if args.start else config.dataset.target_start
    end = parse_date(args.end) if args.end else config.dataset.target_end
    if _aspect_only_mode(args):
        if args.aspect_year is not None:
            aspect_start = parse_date(f"{args.aspect_year}-01-01")
            aspect_end = parse_date(f"{args.aspect_year}-12-31")
        else:
            aspect_start = parse_date(args.aspect_start) if args.aspect_start else start
            aspect_end = parse_date(args.aspect_end) if args.aspect_end else end
        pairs = resolve_aspect_pairs(
            profile=args.aspect_profile,
            aspect_bodies=args.aspect_bodies,
            aspect_pairs=args.aspect_pairs,
            include_moon_aspects=args.include_moon_aspects == "true" or args.aspect_profile in {"all", "lunar_short_term"},
        )
        tasks = aspect_tasks(pairs=pairs, start=aspect_start, end=aspect_end)
        results = build_aspect_chunks(
            config_path=ROOT / args.config,
            output_dir=ROOT / args.write_parquet,
            tasks=tasks,
            skip_existing=args.skip_existing,
            resume=args.resume,
            workers=max(1, args.workers),
            write_parquet=not args.no_parquet,
        )
        warnings = validate_aspect_chunks(
            output_dir=ROOT / args.write_parquet,
            tasks=tasks,
            expected_min_ts=datetime(aspect_start.year, aspect_start.month, aspect_start.day, tzinfo=UTC),
            expected_max_ts=datetime(aspect_end.year, aspect_end.month, aspect_end.day, 23, 59, 59, tzinfo=UTC),
        )
        print("Astro aspect chunk build complete")
        print(f"dataset_id={config.dataset.dataset_id} range={aspect_start}->{aspect_end} pairs={len(pairs)} tasks={len(tasks)} workers={args.workers}")
        print(f"built={sum(1 for row in results if row['status'] == 'built')} skipped={sum(1 for row in results if row['status'] == 'skipped')}")
        print(f"events={sum(int(row.get('events', 0)) for row in results)} windows={sum(int(row.get('windows', 0)) for row in results)}")
        for row in results[:20]:
            print(f"{row['status']} year={row['year']} pair={row['pair']} events={row.get('events', '-') } seconds={row.get('seconds', '-')}")
        for warning in warnings:
            print(f"warning={warning}")
        print(f"output_dir={ROOT / args.write_parquet / 'aspects'}")
        return 0

    dataset = build_astro_daily_dataset(config, start=start, end=end)
    warnings = validate_dataset(dataset, start=start, end=end, position_bodies=config.position_bodies)
    paths = export_dataset(dataset, ROOT / args.write_parquet, write_parquet=not args.no_parquet)

    print("Astro daily build complete")
    print(f"dataset_id={config.dataset.dataset_id} range={start}->{end} dry_run={args.dry_run}")
    for key, value in dataset.summary.items():
        print(f"{key}={value}")
    for warning in warnings:
        print(f"warning={warning}")
    print(f"output_dir={ROOT / args.write_parquet}")
    print(f"files={len(paths)}")
    return 0


def _aspect_only_mode(args) -> bool:
    return any(
        (
            args.aspect_profile,
            args.aspect_bodies,
            args.aspect_pairs,
            args.aspect_start,
            args.aspect_end,
            args.aspect_year is not None,
            args.skip_existing,
            args.resume,
            args.workers != 1,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

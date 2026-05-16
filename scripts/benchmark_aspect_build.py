#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.aspect_chunks import AspectBuildTask, build_aspect_chunks
from astro_daily.aspect_profiles import ASPECT_PROFILES, resolve_aspect_pairs
from astro_daily.calendar import parse_date


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark optimized exact aspect chunk builds.")
    parser.add_argument("--config", default="astro_research/configs/astro_daily.yaml")
    parser.add_argument("--profiles", default="macro_core,market_core,lunar_short_term")
    parser.add_argument("--year", type=int, default=2020)
    parser.add_argument("--output-dir", default="astro_research/output/benchmarks/aspects")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit-pairs", type=int, default=None)
    parser.add_argument("--include-moon-aspects", choices=("true", "false"), default="false")
    args = parser.parse_args()

    rows = []
    for profile in [item.strip() for item in args.profiles.split(",") if item.strip()]:
        if profile not in ASPECT_PROFILES:
            raise ValueError(f"Unknown profile: {profile}")
        include_moon = args.include_moon_aspects == "true" or profile == "lunar_short_term"
        pairs = resolve_aspect_pairs(profile=profile, include_moon_aspects=include_moon)
        if args.limit_pairs:
            pairs = pairs[: args.limit_pairs]
        tasks = [
            AspectBuildTask(
                year=args.year,
                pair=pair,
                start=parse_date(f"{args.year}-01-01"),
                end=parse_date(f"{args.year}-12-31"),
            )
            for pair in pairs
        ]
        started = time.perf_counter()
        results = build_aspect_chunks(
            config_path=ROOT / args.config,
            output_dir=ROOT / args.output_dir / profile,
            tasks=tasks,
            skip_existing=False,
            resume=False,
            workers=max(1, args.workers),
            write_parquet=True,
        )
        elapsed = time.perf_counter() - started
        rows.append(
            {
                "profile": profile,
                "year": args.year,
                "pairs": len(pairs),
                "events": sum(int(row.get("events", 0)) for row in results),
                "windows": sum(int(row.get("windows", 0)) for row in results),
                "seconds": round(elapsed, 4),
            }
        )

    print("Aspect Build Benchmark")
    for row in rows:
        print(
            f"{row['profile']} year={row['year']} pairs={row['pairs']} "
            f"events={row['events']} windows={row['windows']} seconds={row['seconds']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from astro_daily.calendar import parse_date
from research.local_data_fetch import ASSET_OUTPUTS, fetch_local_research_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch ignored local long-history research CSV files.")
    parser.add_argument("--asset", action="append", choices=tuple(ASSET_OUTPUTS), help="Asset to fetch. Can be repeated.")
    parser.add_argument("--all", action="store_true", help="Fetch SPX, DXY, Gold, and CreditProxy.")
    parser.add_argument("--start", default="1926-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--fred-api-key-env", default="FRED_API_KEY")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--accept-research-local-terms",
        action="store_true",
        help="Acknowledge that generated local CSVs are for local research only and must not be redistributed from this repo.",
    )
    args = parser.parse_args()

    assets = tuple(ASSET_OUTPUTS) if args.all or not args.asset else tuple(args.asset)
    if not args.dry_run and not args.accept_research_local_terms:
        print(
            "Refusing to fetch local research CSVs without --accept-research-local-terms. "
            "Yahoo/LBMA-derived files are local research inputs and must not be redistributed from this repo.",
            file=sys.stderr,
        )
        return 2

    results = fetch_local_research_data(
        root=ROOT,
        assets=assets,
        start=parse_date(args.start),
        end=parse_date(args.end),
        fred_api_key_env=args.fred_api_key_env,
        dry_run=args.dry_run,
    )
    for result in results:
        print(
            f"{result.asset}: rows={result.rows} coverage={result.coverage_start}->{result.coverage_end} "
            f"source={result.source} output={result.output_path}"
        )
        if result.warning:
            print(f"warning={result.warning}")
    print("provenance=astro_research/data/local/LOCAL_DATA_PROVENANCE.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

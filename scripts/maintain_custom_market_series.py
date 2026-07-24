#!/usr/bin/env python
from __future__ import annotations

import argparse
from datetime import date

from astro_abm.market_series import (
    MarketSeriesStore,
    run_custom_market_series_maintenance,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or incrementally refresh registered custom daily market series."
    )
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    store = MarketSeriesStore()
    records = store.list_for_maintenance()
    if args.dry_run:
        for record in records:
            print(
                f"{record.series_id} symbol={record.symbol} provider={record.provider} "
                f"status={record.status} latest={record.latest_observation_date or 'missing'}"
            )
        print(f"eligible_series={len(records)} dry_run=true")
        return 0

    results = run_custom_market_series_maintenance(
        store=store,
        end=date.fromisoformat(args.end),
    )
    failed = 0
    for result in results:
        print(
            f"{result.series_id} status={result.status} fetched={result.fetched_rows} "
            f"rows={result.rows_written} latest={result.latest_observation_date or 'missing'} "
            f"attempts={result.attempts} errors={len(result.errors)}"
        )
        if result.status != "active":
            failed += 1
    print(f"series={len(results)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from typing import Sequence

from astro_abm.etl.backfill_binance_derivatives import run_binance_derivatives_backfill
from astro_abm.etl.backfill_binance_spot import run_binance_spot_backfill
from astro_abm.etl.backfill_ephemeris import run_ephemeris_backfill
from astro_abm.etl.backfill_noaa_swpc_recent import run_noaa_swpc_recent_backfill
from astro_abm.etl.collect_binance_open_interest import run_binance_open_interest_collect
from astro_abm.etl.maintenance import (
    MaintenanceSummary,
    ensure_utc,
    format_maintenance_summary,
    run_maintenance_tasks,
    split_symbols,
)
from astro_abm.etl.pipeline import normalize_to_utc_hour


def run_hourly_maintenance(
    *,
    run_ts: datetime | None = None,
    symbols: Sequence[str] = ("BTCUSDT", "ETHUSDT"),
    lookback_hours: int = 6,
    collect_market: bool = True,
    collect_derivatives: bool = True,
    collect_current_open_interest: bool = True,
    collect_space_weather_recent: bool = True,
    collect_ephemeris: bool = True,
) -> MaintenanceSummary:
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be greater than 0.")
    symbol_list = split_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    bucket_ts = normalize_to_utc_hour(ensure_utc(run_ts or datetime.now(UTC)))
    window_start = bucket_ts - timedelta(hours=lookback_hours)
    complete_market_end = bucket_ts
    current_window_end = bucket_ts + timedelta(hours=1)

    tasks = []
    if collect_market:
        tasks.append(
            (
                "binance_spot_recent",
                lambda: run_binance_spot_backfill(
                    symbols=symbol_list,
                    start_utc=window_start,
                    end_utc=complete_market_end,
                ),
            )
        )
    if collect_derivatives:
        tasks.append(
            (
                "binance_derivatives_recent",
                lambda: run_binance_derivatives_backfill(
                    symbols=symbol_list,
                    start_utc=window_start,
                    end_utc=complete_market_end,
                    include_open_interest=True,
                ),
            )
        )
    if collect_current_open_interest:
        tasks.append(
            (
                "binance_current_open_interest",
                lambda: run_binance_open_interest_collect(symbols=symbol_list, run_ts=bucket_ts),
            )
        )
    if collect_space_weather_recent:
        tasks.append(
            (
                "noaa_swpc_recent",
                lambda: run_noaa_swpc_recent_backfill(
                    start_utc=window_start,
                    end_utc=current_window_end,
                ),
            )
        )
    if collect_ephemeris:
        tasks.append(
            (
                "ephemeris_current_hour",
                lambda: run_ephemeris_backfill(
                    start_utc=bucket_ts,
                    end_utc=current_window_end,
                    chunk_days=1,
                ),
            )
        )

    return MaintenanceSummary(
        run_ts=bucket_ts,
        window_start=window_start,
        window_end=current_window_end,
        tasks=run_maintenance_tasks(tasks),
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _env_symbols() -> tuple[str, ...]:
    return split_symbols(os.getenv("ASTRO_ABM_CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run hourly Astro ABM data maintenance without social sentiment.")
    parser.add_argument("--run-ts", default=None, help="UTC timestamp to align to, defaults to now.")
    parser.add_argument("--symbols", default=",".join(_env_symbols()), help="Comma-separated Binance symbols.")
    parser.add_argument("--lookback-hours", type=int, default=6, help="Recent window to refresh.")
    parser.add_argument("--skip-market", action="store_true", help="Skip Binance spot OHLCV refresh.")
    parser.add_argument("--skip-derivatives", action="store_true", help="Skip Binance derivatives refresh.")
    parser.add_argument("--skip-current-oi", action="store_true", help="Skip Binance current open-interest snapshot.")
    parser.add_argument("--skip-swpc", action="store_true", help="Skip NOAA SWPC recent refresh.")
    parser.add_argument("--skip-ephemeris", action="store_true", help="Skip current-hour ephemeris.")
    args = parser.parse_args(argv)

    summary = run_hourly_maintenance(
        run_ts=_parse_utc(args.run_ts) if args.run_ts else None,
        symbols=split_symbols(args.symbols),
        lookback_hours=args.lookback_hours,
        collect_market=not args.skip_market,
        collect_derivatives=not args.skip_derivatives,
        collect_current_open_interest=not args.skip_current_oi,
        collect_space_weather_recent=not args.skip_swpc,
        collect_ephemeris=not args.skip_ephemeris,
    )
    print(format_maintenance_summary(summary, title="Hourly Maintenance Summary"))
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

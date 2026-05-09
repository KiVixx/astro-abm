from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from typing import Sequence

from astro_abm.etl.backfill_binance_vision_metrics import run_binance_vision_metrics_backfill
from astro_abm.etl.backfill_ephemeris import run_ephemeris_backfill
from astro_abm.etl.backfill_goes_xray import run_goes_xray_backfill
from astro_abm.etl.backfill_noaa_swpc_recent import run_noaa_swpc_recent_backfill
from astro_abm.etl.backfill_space_weather import run_space_weather_backfill
from astro_abm.etl.maintenance import (
    MaintenanceSummary,
    ensure_utc,
    format_maintenance_summary,
    run_maintenance_tasks,
    split_symbols,
)
from astro_abm.etl.pipeline import normalize_to_utc_hour


def run_daily_maintenance(
    *,
    run_ts: datetime | None = None,
    symbols: Sequence[str] = ("BTCUSDT", "ETHUSDT"),
    archive_lookback_days: int = 7,
    swpc_lookback_days: int = 3,
    omni_lookback_days: int = 75,
    ephemeris_lookback_days: int = 1,
    ephemeris_forward_days: int = 2,
    refresh_binance_vision: bool = True,
    refresh_goes_xray: bool = True,
    refresh_swpc_recent: bool = True,
    refresh_omni: bool = True,
    refresh_ephemeris: bool = True,
) -> MaintenanceSummary:
    if archive_lookback_days <= 0:
        raise ValueError("archive_lookback_days must be greater than 0.")
    if swpc_lookback_days <= 0:
        raise ValueError("swpc_lookback_days must be greater than 0.")
    if omni_lookback_days <= 0:
        raise ValueError("omni_lookback_days must be greater than 0.")
    symbol_list = split_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    bucket_ts = normalize_to_utc_hour(ensure_utc(run_ts or datetime.now(UTC)))
    archive_start = bucket_ts - timedelta(days=archive_lookback_days)
    swpc_start = bucket_ts - timedelta(days=swpc_lookback_days)
    omni_start = bucket_ts - timedelta(days=omni_lookback_days)
    ephemeris_start = bucket_ts - timedelta(days=ephemeris_lookback_days)
    ephemeris_end = bucket_ts + timedelta(days=ephemeris_forward_days)

    tasks = []
    summary_starts: list[datetime] = []
    summary_ends: list[datetime] = []
    if refresh_binance_vision:
        summary_starts.append(archive_start)
        summary_ends.append(bucket_ts)
        tasks.append(
            (
                "binance_vision_metrics_recent",
                lambda: run_binance_vision_metrics_backfill(
                    symbols=symbol_list,
                    start_utc=archive_start,
                    end_utc=bucket_ts,
                ),
            )
        )
    if refresh_goes_xray:
        summary_starts.append(archive_start)
        summary_ends.append(bucket_ts)
        tasks.append(
            (
                "goes_xray_recent",
                lambda: run_goes_xray_backfill(
                    start_utc=archive_start,
                    end_utc=bucket_ts,
                ),
            )
        )
    if refresh_swpc_recent:
        summary_starts.append(swpc_start)
        summary_ends.append(bucket_ts)
        tasks.append(
            (
                "noaa_swpc_recent_overlay",
                lambda: run_noaa_swpc_recent_backfill(
                    start_utc=swpc_start,
                    end_utc=bucket_ts,
                ),
            )
        )
    if refresh_omni:
        summary_starts.append(omni_start)
        summary_ends.append(bucket_ts)
        tasks.append(
            (
                "nasa_omni_recent_authoritative",
                lambda: run_space_weather_backfill(
                    start_utc=omni_start,
                    end_utc=bucket_ts,
                ),
            )
        )
    if refresh_ephemeris:
        summary_starts.append(ephemeris_start)
        summary_ends.append(ephemeris_end)
        tasks.append(
            (
                "ephemeris_recent_and_forward",
                lambda: run_ephemeris_backfill(
                    start_utc=ephemeris_start,
                    end_utc=ephemeris_end,
                    chunk_days=max(1, ephemeris_lookback_days + ephemeris_forward_days),
                ),
            )
        )
    return MaintenanceSummary(
        run_ts=bucket_ts,
        window_start=min(summary_starts) if summary_starts else bucket_ts,
        window_end=max(summary_ends) if summary_ends else bucket_ts,
        tasks=run_maintenance_tasks(tasks),
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _env_symbols(name: str, default: str) -> tuple[str, ...]:
    return split_symbols(os.getenv(name, default))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run daily Astro ABM archive/data-health maintenance.")
    parser.add_argument("--run-ts", default=None, help="UTC timestamp to align to, defaults to now.")
    parser.add_argument("--symbols", default=",".join(_env_symbols("ASTRO_ABM_CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT")))
    parser.add_argument("--archive-lookback-days", type=int, default=7)
    parser.add_argument("--swpc-lookback-days", type=int, default=3)
    parser.add_argument("--omni-lookback-days", type=int, default=75)
    parser.add_argument("--ephemeris-lookback-days", type=int, default=1)
    parser.add_argument("--ephemeris-forward-days", type=int, default=2)
    parser.add_argument("--skip-binance-vision", action="store_true")
    parser.add_argument("--skip-goes-xray", action="store_true")
    parser.add_argument("--skip-swpc", action="store_true")
    parser.add_argument("--skip-omni", action="store_true")
    parser.add_argument("--skip-ephemeris", action="store_true")
    args = parser.parse_args(argv)

    summary = run_daily_maintenance(
        run_ts=_parse_utc(args.run_ts) if args.run_ts else None,
        symbols=split_symbols(args.symbols),
        archive_lookback_days=args.archive_lookback_days,
        swpc_lookback_days=args.swpc_lookback_days,
        omni_lookback_days=args.omni_lookback_days,
        ephemeris_lookback_days=args.ephemeris_lookback_days,
        ephemeris_forward_days=args.ephemeris_forward_days,
        refresh_binance_vision=not args.skip_binance_vision,
        refresh_goes_xray=not args.skip_goes_xray,
        refresh_swpc_recent=not args.skip_swpc,
        refresh_omni=not args.skip_omni,
        refresh_ephemeris=not args.skip_ephemeris,
    )
    print(format_maintenance_summary(summary, title="Daily Maintenance Summary"))
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import os
import signal
import time
from datetime import UTC, datetime
from typing import Callable, Literal, Sequence

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from astro_abm.etl.maintain_daily import run_daily_maintenance
from astro_abm.etl.maintain_hourly import run_hourly_maintenance
from astro_abm.etl.maintenance import format_maintenance_summary, split_symbols


RunOnStart = Literal["none", "hourly", "daily", "both"]


def build_maintenance_scheduler(
    *,
    symbols: Sequence[str],
    timezone: str = "UTC",
    enable_hourly: bool = True,
    enable_daily: bool = True,
    daily_hour: int = 0,
    daily_minute: int = 20,
    ephemeris_forward_days: int = 370,
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=timezone)
    if enable_hourly:
        scheduler.add_job(
            _job_runner(
                "hourly",
                lambda: run_hourly_maintenance(symbols=symbols),
                title="Hourly Maintenance Summary",
            ),
            trigger=CronTrigger(minute=5, timezone=timezone),
            id="hourly_maintenance",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=900,
        )
    if enable_daily:
        scheduler.add_job(
            _job_runner(
                "daily",
                lambda: run_daily_maintenance(symbols=symbols, ephemeris_forward_days=ephemeris_forward_days),
                title="Daily Maintenance Summary",
            ),
            trigger=CronTrigger(hour=daily_hour, minute=daily_minute, timezone=timezone),
            id="daily_maintenance",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
    return scheduler


def run_daemon(
    *,
    symbols: Sequence[str],
    timezone: str = "UTC",
    enable_hourly: bool = True,
    enable_daily: bool = True,
    daily_hour: int = 0,
    daily_minute: int = 20,
    ephemeris_forward_days: int = 370,
    run_on_start: RunOnStart = "none",
) -> int:
    scheduler = build_maintenance_scheduler(
        symbols=symbols,
        timezone=timezone,
        enable_hourly=enable_hourly,
        enable_daily=enable_daily,
        daily_hour=daily_hour,
        daily_minute=daily_minute,
        ephemeris_forward_days=ephemeris_forward_days,
    )
    stopped = False

    def stop(_signum, _frame):
        nonlocal stopped
        stopped = True
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    print(
        "Astro ABM maintenance daemon starting: "
        f"hourly={enable_hourly} daily={enable_daily} timezone={timezone} "
        f"daily={daily_hour:02d}:{daily_minute:02d} "
        f"ephemeris_forward_days={ephemeris_forward_days} run_on_start={run_on_start}",
        flush=True,
    )
    if run_on_start in {"hourly", "both"} and enable_hourly:
        _job_runner("hourly", lambda: run_hourly_maintenance(symbols=symbols), title="Hourly Maintenance Summary")()
    if run_on_start in {"daily", "both"} and enable_daily:
        _job_runner(
            "daily",
            lambda: run_daily_maintenance(symbols=symbols, ephemeris_forward_days=ephemeris_forward_days),
            title="Daily Maintenance Summary",
        )()

    scheduler.start()
    while not stopped:
        time.sleep(1)
    print("Astro ABM maintenance daemon stopped.", flush=True)
    return 0


def _job_runner(name: str, func: Callable, *, title: str) -> Callable[[], None]:
    def run_job() -> None:
        print(f"==== {name} maintenance start {datetime.now(UTC).isoformat()} ====", flush=True)
        try:
            summary = func()
            print(format_maintenance_summary(summary, title=title), flush=True)
        except Exception as exc:
            print(f"{name} maintenance failed: {type(exc).__name__}: {exc}", flush=True)
        print(f"==== {name} maintenance end {datetime.now(UTC).isoformat()} ====", flush=True)

    return run_job


def _env_symbols(name: str, default: str) -> tuple[str, ...]:
    return split_symbols(os.getenv(name, default))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Astro ABM hourly/daily maintenance on a scheduler.")
    parser.add_argument("--symbols", default=",".join(_env_symbols("ASTRO_ABM_CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT")))
    parser.add_argument("--timezone", default=os.getenv("ASTRO_ABM_SCHEDULER_TZ", "UTC"))
    parser.add_argument("--no-hourly", action="store_true", help="Disable hourly maintenance.")
    parser.add_argument("--no-daily", action="store_true", help="Disable daily maintenance.")
    parser.add_argument("--daily-hour", type=int, default=int(os.getenv("ASTRO_ABM_DAILY_HOUR", "0")))
    parser.add_argument("--daily-minute", type=int, default=int(os.getenv("ASTRO_ABM_DAILY_MINUTE", "20")))
    parser.add_argument(
        "--ephemeris-forward-days",
        type=int,
        default=int(os.getenv("ASTRO_ABM_EPHEMERIS_FORWARD_DAYS", "370")),
    )
    parser.add_argument("--run-on-start", choices=("none", "hourly", "daily", "both"), default=os.getenv("ASTRO_ABM_RUN_ON_START", "none"))
    args = parser.parse_args(argv)
    return run_daemon(
        symbols=split_symbols(args.symbols),
        timezone=args.timezone,
        enable_hourly=not args.no_hourly,
        enable_daily=not args.no_daily,
        daily_hour=args.daily_hour,
        daily_minute=args.daily_minute,
        ephemeris_forward_days=args.ephemeris_forward_days,
        run_on_start=args.run_on_start,
    )


if __name__ == "__main__":
    raise SystemExit(main())

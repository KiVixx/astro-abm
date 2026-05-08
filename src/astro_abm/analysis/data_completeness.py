from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Sequence

from astro_abm.storage.questdb import QuestDBMarketBarWriter


def load_data_completeness_report(*, recent_runs: int = 10, connection_factory=None) -> dict:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT symbol, source, count(), min(ts), max(ts)
                FROM market_ohlcv_1h
                GROUP BY symbol, source
                ORDER BY symbol, source
                """.strip()
            )
            market_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT source, entity_type, entity_id, metric_name, quality_flag, count(), min(ts), max(ts)
                FROM abm_hourly_facts
                WHERE entity_id != 'TEST'
                GROUP BY source, entity_type, entity_id, metric_name, quality_flag
                ORDER BY source, entity_type, entity_id, metric_name, quality_flag
                """.strip()
            )
            fact_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT source, metric_name, quality_flag, count(), min(ts), max(ts)
                FROM v_space_weather_unified
                GROUP BY source, metric_name, quality_flag
                ORDER BY metric_name, source, quality_flag
                """.strip()
            )
            space_weather_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT source, entity_id, metric_name, quality_flag, count(), min(ts), max(ts)
                FROM v_open_interest_unified
                GROUP BY source, entity_id, metric_name, quality_flag
                ORDER BY entity_id, metric_name, source, quality_flag
                """.strip()
            )
            open_interest_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT job_type, provider, status, rows_written, skipped_existing, errors, window_start, window_end, finished_at
                FROM etl_runs
                ORDER BY started_at DESC
                LIMIT %s
                """.strip(),
                (recent_runs,),
            )
            etl_runs = cursor.fetchall()

    return {
        "market_rows": market_rows,
        "fact_rows": fact_rows,
        "space_weather_rows": space_weather_rows,
        "open_interest_rows": open_interest_rows,
        "etl_runs": etl_runs,
    }


def format_data_completeness_report(report: dict, *, as_of: datetime | None = None) -> str:
    as_of = _ensure_utc(as_of or datetime.now(UTC))
    lines = [
        "Data Completeness Report",
        f"As of: {as_of.isoformat()}",
        "",
        "Market OHLCV",
    ]
    lines.extend(_format_market_rows(report.get("market_rows", ()), as_of=as_of))
    lines.extend(["", "Unified Space Weather"])
    lines.extend(_format_space_weather_rows(report.get("space_weather_rows", ()), as_of=as_of))
    lines.extend(["", "Unified Open Interest"])
    lines.extend(_format_open_interest_rows(report.get("open_interest_rows", ()), as_of=as_of))
    lines.extend(["", "Hourly Facts"])
    lines.extend(_format_fact_rows(report.get("fact_rows", ()), as_of=as_of))
    lines.extend(["", "Recent ETL Runs"])
    lines.extend(_format_etl_runs(report.get("etl_runs", ())))
    return "\n".join(lines)


def _format_market_rows(rows, *, as_of: datetime) -> list[str]:
    if not rows:
        return ["  - none"]
    return [
        (
            f"  - {symbol}/{source}: rows={count} range={_range_text(min_ts, max_ts)} "
            f"lag={_lag_text(max_ts, as_of)} health={_health_text(max_ts, as_of, _stale_after_hours('market', source, None))}"
        )
        for symbol, source, count, min_ts, max_ts in rows
    ]


def _format_space_weather_rows(rows, *, as_of: datetime) -> list[str]:
    if not rows:
        return ["  - none"]
    return [
        (
            f"  - {metric_name} [{source}/{quality_flag}]: rows={count} range={_range_text(min_ts, max_ts)} "
            f"lag={_lag_text(max_ts, as_of)} "
            f"health={_health_text(max_ts, as_of, _stale_after_hours('space_weather', source, metric_name))}"
        )
        for source, metric_name, quality_flag, count, min_ts, max_ts in rows
    ]


def _format_open_interest_rows(rows, *, as_of: datetime) -> list[str]:
    if not rows:
        return ["  - none"]
    return [
        (
            f"  - {entity_id}/{metric_name} [{source}/{quality_flag}]: rows={count} range={_range_text(min_ts, max_ts)} "
            f"lag={_lag_text(max_ts, as_of)} "
            f"health={_health_text(max_ts, as_of, _stale_after_hours('open_interest', source, metric_name))}"
        )
        for source, entity_id, metric_name, quality_flag, count, min_ts, max_ts in rows
    ]


def _format_fact_rows(rows, *, as_of: datetime) -> list[str]:
    if not rows:
        return ["  - none"]
    return [
        (
            f"  - {source}/{entity_type}/{entity_id}/{metric_name}"
            f" [{quality_flag or 'unknown'}]: rows={count} range={_range_text(min_ts, max_ts)} "
            f"lag={_lag_text(max_ts, as_of)} "
            f"health={_health_text(max_ts, as_of, _stale_after_hours('fact', source, metric_name))}"
        )
        for source, entity_type, entity_id, metric_name, quality_flag, count, min_ts, max_ts in rows
    ]


def _format_etl_runs(rows) -> list[str]:
    if not rows:
        return ["  - none"]
    return [
        (
            f"  - {job_type}/{provider}/{status}: rows={rows_written} skipped={skipped_existing} "
            f"errors={errors} window={_range_text(window_start, window_end)} finished={_time_text(finished_at)}"
        )
        for job_type, provider, status, rows_written, skipped_existing, errors, window_start, window_end, finished_at in rows
    ]


def _range_text(start, end) -> str:
    return f"{_time_text(start)} -> {_time_text(end)}"


def _time_text(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, datetime):
        return _ensure_utc(value).strftime("%Y-%m-%d %H:%M")
    return str(value)


def _lag_text(max_ts, as_of: datetime) -> str:
    if max_ts is None:
        return "unknown"
    max_utc = _ensure_utc(max_ts)
    lag_hours = max(0.0, (as_of - max_utc).total_seconds() / 3600)
    if lag_hours < 48:
        return f"{lag_hours:.1f}h"
    return f"{lag_hours / 24:.1f}d"


def _health_text(max_ts, as_of: datetime, stale_after_hours: float) -> str:
    if max_ts is None:
        return "MISSING"
    max_utc = _ensure_utc(max_ts)
    lag_hours = max(0.0, (as_of - max_utc).total_seconds() / 3600)
    return "OK" if lag_hours <= stale_after_hours else "STALE"


def _stale_after_hours(section: str, source: str, metric_name: str | None) -> float:
    if source == "nasa_omni":
        return 75 * 24
    if source in {"binance_vision_metrics", "noaa_goes_xrs"}:
        return 7 * 24
    if source == "coinalyze_daily":
        return 3 * 24
    if source == "pyswisseph":
        return 24
    if section == "space_weather" and source == "noaa_swpc_recent":
        return 48
    if metric_name == "funding_rate":
        return 12
    return 48


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print QuestDB data completeness coverage by source, metric, and quality flag.")
    parser.add_argument("--recent-runs", type=int, default=10, help="Number of recent ETL runs to include.")
    args = parser.parse_args(argv)
    print(format_data_completeness_report(load_data_completeness_report(recent_runs=args.recent_runs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

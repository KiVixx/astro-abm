from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import Sequence

from astro_abm.storage.questdb import QuestDBMarketBarWriter


INACTIVE_SOURCES = (
    "ASKGROK_WEB",
    "lunarcrush",
    "coinalyze",
    "coinalyze_1h",
    "coinalyze_daily",
    "noaa_swpc",
    "polygon",
    "tardis_binance_futures",
)


def load_data_completeness_report(*, recent_runs: int = 10, active_only: bool = True, connection_factory=None) -> dict:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    inactive_filter = _inactive_source_filter(active_only)
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT symbol, source, count(), min(ts), max(ts)
                FROM market_ohlcv_1h
                {inactive_filter}
                GROUP BY symbol, source
                ORDER BY symbol, source
                """.strip()
            )
            market_rows = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT symbol, source, ts
                FROM market_ohlcv_1h
                {inactive_filter}
                ORDER BY symbol, source, ts
                """.strip()
            )
            market_timestamp_rows = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT source, entity_type, entity_id, metric_name, quality_flag, count(), min(ts), max(ts)
                FROM abm_hourly_facts
                WHERE entity_id != 'TEST'
                {_inactive_source_filter(active_only, prefix="AND")}
                {_active_fact_quality_filter(active_only)}
                GROUP BY source, entity_type, entity_id, metric_name, quality_flag
                ORDER BY source, entity_type, entity_id, metric_name, quality_flag
                """.strip()
            )
            fact_rows = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT source, metric_name, quality_flag, count(), min(ts), max(ts)
                FROM v_space_weather_unified
                {inactive_filter}
                GROUP BY source, metric_name, quality_flag
                ORDER BY metric_name, source, quality_flag
                """.strip()
            )
            space_weather_rows = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT source, entity_id, metric_name, quality_flag, count(), min(ts), max(ts)
                FROM v_open_interest_unified
                {inactive_filter}
                GROUP BY source, entity_id, metric_name, quality_flag
                ORDER BY entity_id, metric_name, source, quality_flag
                """.strip()
            )
            open_interest_rows = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT job_type, provider, status, rows_written, skipped_existing, errors, window_start, window_end, finished_at
                FROM etl_runs
                {_inactive_source_filter(active_only, column="provider")}
                ORDER BY started_at DESC
                LIMIT %s
                """.strip(),
                (recent_runs,),
            )
            etl_runs = cursor.fetchall()

    return {
        "market_rows": market_rows,
        "market_gap_rows": _summarize_market_gaps(market_timestamp_rows),
        "fact_rows": fact_rows,
        "space_weather_rows": space_weather_rows,
        "open_interest_rows": open_interest_rows,
        "etl_runs": etl_runs,
        "active_only": active_only,
    }


def format_data_completeness_report(report: dict, *, as_of: datetime | None = None) -> str:
    as_of = _ensure_utc(as_of or datetime.now(UTC))
    lines = [
        "Data Completeness Report",
        f"As of: {as_of.isoformat()}",
        f"Scope: {'active sources only' if report.get('active_only', True) else 'all sources'}",
        "",
        "Market OHLCV",
    ]
    lines.extend(_format_market_rows(report.get("market_rows", ()), as_of=as_of))
    lines.extend(["", "Market OHLCV Gaps"])
    lines.extend(_format_market_gap_rows(report.get("market_gap_rows", ())))
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


def _format_market_gap_rows(rows) -> list[str]:
    if not rows:
        return ["  - none"]
    return [
        (
            f"  - {symbol}/{source}: missing_hours={missing_hours} gap_segments={gap_segments} "
            f"first_gap={_range_text(first_gap_start, first_gap_end)} "
            f"last_gap={_range_text(last_gap_start, last_gap_end)}"
        )
        for symbol, source, gap_segments, missing_hours, first_gap_start, first_gap_end, last_gap_start, last_gap_end in rows
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
    if source == "ccdata_aggregate":
        return 20 * 365 * 24
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


def _inactive_source_filter(active_only: bool, *, column: str = "source", prefix: str = "WHERE") -> str:
    if not active_only:
        return ""
    sources = ", ".join(f"'{source}'" for source in INACTIVE_SOURCES)
    return f"{prefix} {column} NOT IN ({sources})"


def _summarize_market_gaps(rows) -> list[tuple]:
    by_key: dict[tuple[str, str], list[datetime]] = {}
    for symbol, source, ts in rows:
        if source == "ccdata_aggregate":
            continue
        by_key.setdefault((symbol, source), []).append(_ensure_utc(ts))

    summaries = []
    for (symbol, source), timestamps in by_key.items():
        if len(timestamps) < 2:
            continue
        gaps = []
        previous = timestamps[0]
        for current in timestamps[1:]:
            if current - previous > timedelta(hours=1):
                gaps.append((previous + timedelta(hours=1), current, int((current - previous).total_seconds() // 3600) - 1))
            previous = current
        if not gaps:
            continue
        summaries.append(
            (
                symbol,
                source,
                len(gaps),
                sum(gap[2] for gap in gaps),
                gaps[0][0],
                gaps[0][1],
                gaps[-1][0],
                gaps[-1][1],
            )
        )
    return summaries


def _active_fact_quality_filter(active_only: bool) -> str:
    if not active_only:
        return ""
    return """
                AND NOT (source = 'binance' AND entity_type = 'crypto_ohlcv')
                AND NOT (source IN ('nasa_omni', 'noaa_goes_xrs', 'pyswisseph') AND quality_flag IN ('derived', 'final'))
    """.rstrip()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print QuestDB data completeness coverage by source, metric, and quality flag.")
    parser.add_argument("--recent-runs", type=int, default=10, help="Number of recent ETL runs to include.")
    parser.add_argument("--include-inactive", action="store_true", help="Include disabled/archive providers such as ASKGROK, LunarCrush, Coinalyze, and Tardis.")
    args = parser.parse_args(argv)
    print(
        format_data_completeness_report(
            load_data_completeness_report(recent_runs=args.recent_runs, active_only=not args.include_inactive)
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

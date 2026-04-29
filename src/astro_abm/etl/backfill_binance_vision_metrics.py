from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence
from uuid import uuid4

import requests

from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.market_data.binance_vision_metrics import (
    BinanceVisionMetricsClient,
    aggregate_binance_vision_metrics_hourly,
    build_binance_vision_metric_feature_rows,
    iter_days,
    parse_binance_vision_metrics_file,
)
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class BinanceVisionMetricsBackfillSummary:
    days_seen: int
    fetched_files: int
    missing_files: int
    records_seen: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]
    run_id: str


def run_binance_vision_metrics_backfill(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    client: BinanceVisionMetricsClient | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    cache_dir: Path | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> BinanceVisionMetricsBackfillSummary:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    run_id = run_id or f"binance-vision-metrics-{uuid4().hex}"
    started_at = datetime.now(UTC)
    client = client or BinanceVisionMetricsClient()
    writer = writer or QuestDBHourlyFactWriter()
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=writer.connection_factory)
    cache_dir = cache_dir or Path.home() / ".cache" / "astro-abm"

    days_seen = 0
    fetched_files = 0
    missing_files = 0
    records_seen = 0
    written = 0
    skipped = 0
    errors: list[str] = []

    for symbol in symbol_list:
        for day in iter_days(start_utc, end_utc):
            days_seen += 1
            day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
            day_end = day_start + timedelta(days=1)
            try:
                path = client.download_daily_metrics_zip(symbol=symbol, day=day, cache_dir=cache_dir)
                fetched_files += 1
                records = parse_binance_vision_metrics_file(path)
                records_seen += len(records)
                hourly = [
                    record
                    for record in aggregate_binance_vision_metrics_hourly(records)
                    if start_utc <= record.ts < end_utc
                ]
                rows = build_binance_vision_metric_feature_rows(hourly)
                rows, row_skipped = _filter_existing(
                    rows,
                    connection_factory=writer.connection_factory,
                    entity_id=symbol,
                    start_utc=max(start_utc, day_start),
                    end_utc=min(end_utc, day_end),
                )
                skipped += row_skipped
                rows = [{**row, "ingest_run_id": run_id} for row in rows]
                writer.write(rows)
                written += len(rows)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    missing_files += 1
                    continue
                errors.append(f"{symbol}:{day.isoformat()}:{type(exc).__name__}:{exc}")
            except Exception as exc:
                errors.append(f"{symbol}:{day.isoformat()}:{type(exc).__name__}:{exc}")

    if record_run:
        status = "success" if not errors else "partial" if written else "failed"
        run_writer.write(
            ETLRunRecord(
                started_at=started_at,
                run_id=run_id,
                job_type="binance_vision_metrics_backfill",
                provider="binance_vision_metrics",
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes=(
                    "Binance Vision UM daily metrics. Hourly rows are last available 5m snapshot per hour. "
                    f"missing_files={missing_files}"
                ),
            )
        )

    return BinanceVisionMetricsBackfillSummary(
        days_seen=days_seen,
        fetched_files=fetched_files,
        missing_files=missing_files,
        records_seen=records_seen,
        written=written,
        skipped_existing=skipped,
        errors=tuple(errors),
        run_id=run_id,
    )


def _filter_existing(rows, *, connection_factory, entity_id: str, start_utc: datetime, end_utc: datetime):
    metric_names = {
        "open_interest",
        "open_interest_value",
        "count_toptrader_long_short_ratio",
        "sum_toptrader_long_short_ratio",
        "count_long_short_ratio",
        "sum_taker_long_short_vol_ratio",
    }
    existing_by_metric = {
        metric_name: load_existing_fact_timestamps(
            connection_factory,
            entity_id=entity_id,
            source="binance_vision_metrics",
            metric_name=metric_name,
            start_ts=start_utc,
            end_ts=end_utc,
        )
        for metric_name in metric_names
    }
    new_rows = [
        row
        for row in rows
        if row["ts"] not in existing_by_metric.get(row["metric_name"], set())
    ]
    return new_rows, len(rows) - len(new_rows)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill Binance Vision futures metrics into hourly facts.")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="Comma-separated symbols.")
    parser.add_argument("--start", default="2020-09-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--cache-dir", default=None, help="Directory for downloaded Binance Vision zip files.")
    args = parser.parse_args(argv)
    result = run_binance_vision_metrics_backfill(
        symbols=normalize_symbols(args.symbols.split(",")),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )
    print(
        "Binance Vision metrics backfill complete: "
        f"days_seen={result.days_seen} fetched_files={result.fetched_files} "
        f"missing_files={result.missing_files} "
        f"records_seen={result.records_seen} written={result.written} "
        f"skipped_existing={result.skipped_existing} errors={len(result.errors)} "
        f"run_id={result.run_id}"
    )
    if result.errors:
        for error in result.errors[:10]:
            print(f"error: {error}")
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

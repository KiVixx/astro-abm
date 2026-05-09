from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Sequence
from uuid import uuid4

import pandas as pd

from astro_abm.features.price_action import build_price_action_feature_rows
from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
)


@dataclass(frozen=True)
class PriceFeatureBuildResult:
    read_bars: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...] = ()
    run_id: str = ""


def run_price_feature_build(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    source: str = "binance",
    chunk_days: int = 90,
    connection_factory: Callable | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> PriceFeatureBuildResult:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    writer = writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=connection_factory)
    run_id = run_id or f"price-action-{uuid4().hex}"
    started_at = datetime.now(UTC)
    read_bars = 0
    written = 0
    skipped = 0
    errors: list[str] = []

    for symbol in symbol_list:
        for chunk_start, chunk_end in _time_chunks(start_utc, end_utc, chunk_days=chunk_days):
            try:
                query_start = chunk_start - timedelta(hours=24)
                frame = _load_market_frame(
                    connection_factory,
                    symbol=symbol,
                    source=source,
                    start_utc=query_start,
                    end_utc=chunk_end,
                )
                read_bars += len(frame)
                if frame.empty:
                    continue

                rows = [
                    {**row, "ingest_run_id": run_id}
                    for row in build_price_action_feature_rows(frame)
                    if chunk_start <= row["ts"] < chunk_end
                ]
                existing = _load_existing_price_action_keys(
                    connection_factory,
                    entity_id=symbol,
                    start_ts=chunk_start,
                    end_ts=chunk_end,
                )
                new_rows = [row for row in rows if (row["ts"], row["metric_name"]) not in existing]
                skipped += len(rows) - len(new_rows)
                writer.write(new_rows)
                written += len(new_rows)
            except Exception as exc:
                errors.append(f"{symbol}:{chunk_start.isoformat()}:{type(exc).__name__}:{exc}")

    if record_run:
        status = "success" if not errors else "partial" if written else "failed"
        run_writer.write(
            ETLRunRecord(
                started_at=started_at,
                run_id=run_id,
                job_type="price_feature_build",
                provider="price_action",
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes=f"Built price-action features from market_ohlcv_1h source={source}.",
            )
        )

    return PriceFeatureBuildResult(
        read_bars=read_bars,
        written=written,
        skipped_existing=skipped,
        errors=tuple(errors),
        run_id=run_id,
    )


def _load_market_frame(connection_factory: Callable, *, symbol: str, source: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    sql = """
    SELECT ts, symbol, open, high, low, close, volume, market_type
    FROM market_ohlcv_1h
    WHERE symbol = %s
      AND source = %s
      AND ts >= %s
      AND ts < %s
    ORDER BY ts
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (symbol, source, start_utc, end_utc))
            rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=["ts", "symbol", "open", "high", "low", "close", "volume", "market_type"])


def _load_existing_price_action_keys(
    connection_factory: Callable,
    *,
    entity_id: str,
    start_ts: datetime,
    end_ts: datetime,
) -> set[tuple[datetime, str]]:
    sql = """
    SELECT ts, metric_name
    FROM abm_hourly_facts
    WHERE entity_id = %s
      AND source = 'price_action'
      AND ts >= %s
      AND ts < %s
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (entity_id, start_ts, end_ts))
            return {
                (row[0].replace(tzinfo=start_ts.tzinfo) if row[0].tzinfo is None else row[0], row[1])
                for row in cursor.fetchall()
            }


def _time_chunks(start_utc: datetime, end_utc: datetime, *, chunk_days: int):
    if chunk_days <= 0:
        raise ValueError("chunk_days must be greater than 0.")
    current = start_utc
    step = timedelta(days=chunk_days)
    while current < end_utc:
        next_end = min(end_utc, current + step)
        yield current, next_end
        current = next_end


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build price-action feature rows from market_ohlcv_1h.")
    parser.add_argument("--symbols", default="BTCUSDT", help="Comma-separated symbols.")
    parser.add_argument("--start", default="2017-01-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--source", default="binance", help="Market bar source.")
    parser.add_argument("--chunk-days", type=int, default=90, help="Query/write chunk size in days.")
    args = parser.parse_args(argv)
    result = run_price_feature_build(
        symbols=normalize_symbols(args.symbols.split(",")),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        source=args.source,
        chunk_days=args.chunk_days,
    )
    print(
        "Price-action feature build complete: "
        f"read_bars={result.read_bars} written={result.written} skipped_existing={result.skipped_existing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

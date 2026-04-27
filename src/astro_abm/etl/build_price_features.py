from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Sequence

import pandas as pd

from astro_abm.features.price_action import build_price_action_feature_rows
from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.storage.questdb import (
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class PriceFeatureBuildResult:
    read_bars: int
    written: int
    skipped_existing: int


def run_price_feature_build(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    source: str = "binance",
    chunk_days: int = 90,
    connection_factory: Callable | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
) -> PriceFeatureBuildResult:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    writer = writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    read_bars = 0
    written = 0
    skipped = 0

    for symbol in symbol_list:
        for chunk_start, chunk_end in _time_chunks(start_utc, end_utc, chunk_days=chunk_days):
            query_start = max(start_utc, chunk_start - timedelta(hours=24))
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
                row
                for row in build_price_action_feature_rows(frame)
                if chunk_start <= row["ts"] < chunk_end
            ]
            existing = load_existing_fact_timestamps(
                connection_factory,
                entity_id=symbol,
                source="price_action",
                metric_name="price_return_1h",
                start_ts=chunk_start,
                end_ts=chunk_end,
            )
            new_rows = [row for row in rows if row["ts"] not in existing]
            skipped += len(rows) - len(new_rows)
            writer.write(new_rows)
            written += len(new_rows)

    return PriceFeatureBuildResult(read_bars=read_bars, written=written, skipped_existing=skipped)


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

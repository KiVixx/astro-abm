from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Sequence

from astro_abm.market_data.binance_historical import BinanceSpotHistoricalClient, normalize_symbols
from astro_abm.storage.questdb import (
    QuestDBMarketBarWriter,
    load_existing_market_timestamps,
)


@dataclass(frozen=True)
class SpotBackfillSummary:
    fetched: int
    written: int
    skipped_existing: int


def run_binance_spot_backfill(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    client: BinanceSpotHistoricalClient | None = None,
    writer: QuestDBMarketBarWriter | None = None,
    max_requests: int | None = None,
) -> SpotBackfillSummary:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")

    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    client = client or BinanceSpotHistoricalClient()
    writer = writer or QuestDBMarketBarWriter()
    connection_factory = writer.connection_factory
    fetched = 0
    written = 0
    skipped = 0

    for symbol in symbol_list:
        bars = client.fetch_hourly_klines(
            symbol=symbol,
            start_ts=start_utc,
            end_ts=end_utc,
            max_requests=max_requests,
        )
        fetched += len(bars)
        bars = [bar for bar in bars if start_utc <= bar.ts < end_utc]
        if not bars:
            continue

        existing = load_existing_market_timestamps(
            connection_factory,
            symbol=symbol,
            source="binance",
            start_ts=bars[0].ts,
            end_ts=bars[-1].ts + timedelta(hours=1),
        )
        new_bars = [bar for bar in bars if bar.ts not in existing]
        skipped += len(bars) - len(new_bars)
        writer.write(new_bars)
        written += len(new_bars)

    return SpotBackfillSummary(fetched=fetched, written=written, skipped_existing=skipped)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _split_symbols(value: str) -> tuple[str, ...]:
    return normalize_symbols(value.split(","))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill Binance spot 1h OHLCV into QuestDB.")
    parser.add_argument("--symbols", default="BTCUSDT", help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT.")
    parser.add_argument("--start", default="2017-01-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--max-requests", type=int, default=None, help="Optional safety cap per symbol.")
    args = parser.parse_args(argv)

    result = run_binance_spot_backfill(
        symbols=_split_symbols(args.symbols),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        max_requests=args.max_requests,
    )
    print(
        "Binance spot backfill complete: "
        f"fetched={result.fetched} written={result.written} skipped_existing={result.skipped_existing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

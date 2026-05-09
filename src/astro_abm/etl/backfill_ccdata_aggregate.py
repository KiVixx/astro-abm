from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Sequence
from uuid import uuid4

from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.market_data.ccdata import CCDataAggregateClient
from astro_abm.models import MarketBar
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBMarketBarWriter,
    load_existing_market_timestamps,
)


@dataclass(frozen=True)
class MarketGap:
    symbol: str
    start_ts: datetime
    end_ts: datetime
    missing_hours: int


@dataclass(frozen=True)
class CCDataAggregateBackfillSummary:
    gaps_seen: int
    fetched: int
    written: int
    skipped_existing: int
    missing_from_proxy: int
    run_id: str


def run_ccdata_aggregate_gap_backfill(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    client: CCDataAggregateClient | None = None,
    writer: QuestDBMarketBarWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    context_hours: int = 24,
    request_pause_seconds: float = 2.0,
    record_run: bool = True,
    run_id: str | None = None,
) -> CCDataAggregateBackfillSummary:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    if context_hours <= 0:
        raise ValueError("context_hours must be greater than 0.")
    if request_pause_seconds < 0:
        raise ValueError("request_pause_seconds cannot be negative.")

    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    started_at = datetime.now(UTC)
    run_id = run_id or f"ccdata-aggregate-{uuid4().hex}"
    client = client or CCDataAggregateClient()
    writer = writer or QuestDBMarketBarWriter()
    run_writer = run_writer or QuestDBETLRunWriter(writer.connection_factory)
    connection_factory = writer.connection_factory

    gaps_seen = 0
    fetched = 0
    written = 0
    skipped = 0
    missing_from_proxy = 0

    for symbol in symbol_list:
        gaps = _load_market_gaps(
            connection_factory,
            symbol=symbol,
            source="binance",
            start_utc=start_utc,
            end_utc=end_utc,
        )
        gaps_seen += len(gaps)
        for gap in gaps:
            existing = load_existing_market_timestamps(
                connection_factory,
                symbol=symbol,
                source="ccdata_aggregate",
                start_ts=gap.start_ts,
                end_ts=gap.end_ts,
            )
            if len(existing) >= gap.missing_hours:
                skipped += gap.missing_hours
                continue

            context_start = gap.start_ts - timedelta(hours=context_hours)
            context_end = gap.end_ts + timedelta(hours=context_hours)
            aggregate_bars = client.fetch_hourly_bars(symbol=symbol, start_ts=context_start, end_ts=context_end)
            fetched += len(aggregate_bars)
            aggregate_by_ts = {bar.ts: bar for bar in aggregate_bars}
            binance_by_ts = _load_market_bars(
                connection_factory,
                symbol=symbol,
                source="binance",
                start_utc=context_start,
                end_utc=context_end,
            )
            ratio = _volume_scale_ratio(binance_by_ts=binance_by_ts, aggregate_by_ts=aggregate_by_ts)
            gap_rows = []
            current = gap.start_ts
            while current < gap.end_ts:
                aggregate_bar = aggregate_by_ts.get(current)
                if aggregate_bar is None:
                    missing_from_proxy += 1
                elif current in existing:
                    skipped += 1
                else:
                    gap_rows.append(_scaled_proxy_bar(aggregate_bar, ratio=ratio, run_id=run_id))
                current += timedelta(hours=1)

            writer.write(gap_rows)
            written += len(gap_rows)
            if request_pause_seconds:
                time.sleep(request_pause_seconds)

    if record_run:
        run_writer.write(
            ETLRunRecord(
                started_at=started_at,
                run_id=run_id,
                job_type="ccdata_aggregate_gap_backfill",
                provider="ccdata_aggregate",
                window_start=start_utc,
                window_end=end_utc,
                status="success",
                rows_written=written,
                skipped_existing=skipped,
                errors=0,
                finished_at=datetime.now(UTC),
                notes=(
                    "Backfilled aggregate crypto proxy rows for Binance OHLCV gaps. "
                    f"context_hours={context_hours} request_pause_seconds={request_pause_seconds} "
                    f"gaps_seen={gaps_seen} missing_from_proxy={missing_from_proxy}."
                ),
            )
        )

    return CCDataAggregateBackfillSummary(
        gaps_seen=gaps_seen,
        fetched=fetched,
        written=written,
        skipped_existing=skipped,
        missing_from_proxy=missing_from_proxy,
        run_id=run_id,
    )


def _load_market_gaps(connection_factory, *, symbol: str, source: str, start_utc: datetime, end_utc: datetime) -> list[MarketGap]:
    sql = """
    SELECT ts
    FROM market_ohlcv_1h
    WHERE symbol = %s
      AND source = %s
      AND ts >= %s
      AND ts <= %s
    ORDER BY ts
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (symbol, source, start_utc, end_utc))
            timestamps = [_ensure_utc(row[0]) for row in cursor.fetchall()]

    gaps: list[MarketGap] = []
    previous = None
    for current in timestamps:
        if previous is not None and current - previous > timedelta(hours=1):
            gap_start = previous + timedelta(hours=1)
            gap_end = current
            clipped_start = max(gap_start, start_utc)
            clipped_end = min(gap_end, end_utc)
            if clipped_start < clipped_end:
                gaps.append(
                    MarketGap(
                        symbol=symbol,
                        start_ts=clipped_start,
                        end_ts=clipped_end,
                        missing_hours=int((clipped_end - clipped_start).total_seconds() // 3600),
                    )
                )
        previous = current
    return gaps


def _load_market_bars(connection_factory, *, symbol: str, source: str, start_utc: datetime, end_utc: datetime) -> dict[datetime, MarketBar]:
    sql = """
    SELECT ts, symbol, source, venue, market_type, asset_class, open, high, low, close, volume, quote_volume
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
            return {
                _ensure_utc(row[0]): MarketBar(
                    ts=_ensure_utc(row[0]),
                    symbol=row[1],
                    source=row[2],
                    venue=row[3],
                    market_type=row[4],
                    asset_class=row[5],
                    open=float(row[6]),
                    high=float(row[7]),
                    low=float(row[8]),
                    close=float(row[9]),
                    volume=float(row[10] or 0.0),
                    quote_volume=float(row[11] or 0.0),
                )
                for row in cursor.fetchall()
            }


def _volume_scale_ratio(*, binance_by_ts: dict[datetime, MarketBar], aggregate_by_ts: dict[datetime, MarketBar]) -> float:
    ratios = [
        binance_bar.volume / aggregate_bar.volume
        for ts, binance_bar in binance_by_ts.items()
        if (aggregate_bar := aggregate_by_ts.get(ts)) is not None
        and binance_bar.volume > 0
        and aggregate_bar.volume > 0
    ]
    return float(median(ratios)) if ratios else 1.0


def _scaled_proxy_bar(bar: MarketBar, *, ratio: float, run_id: str) -> MarketBar:
    raw_volume = bar.raw_volume if bar.raw_volume is not None else bar.volume
    raw_quote_volume = bar.raw_quote_volume if bar.raw_quote_volume is not None else bar.quote_volume
    return MarketBar(
        symbol=bar.symbol,
        ts=bar.ts,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=raw_volume * ratio,
        source="ccdata_aggregate",
        venue="ccdata",
        market_type="aggregate_proxy",
        asset_class="crypto",
        quote_volume=raw_quote_volume * ratio if raw_quote_volume is not None else None,
        trade_count=bar.trade_count,
        observed_ts=bar.observed_ts,
        available_ts=bar.available_ts,
        complete=bar.complete,
        quality_flag="proxy",
        is_proxy_data=True,
        is_imputed=False,
        volume_scale_ratio=ratio,
        raw_volume=raw_volume,
        raw_quote_volume=raw_quote_volume,
        conversion_type=bar.conversion_type,
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _split_symbols(value: str) -> tuple[str, ...]:
    return normalize_symbols(value.split(","))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill CCData aggregate proxy 1h OHLCV for Binance gaps.")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT.")
    parser.add_argument("--start", default="2017-01-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--context-hours", type=int, default=24, help="Hours before/after each gap used to scale aggregate volume.")
    parser.add_argument("--request-pause-seconds", type=float, default=2.0, help="Pause between gap requests to avoid CCData rate limits.")
    args = parser.parse_args(argv)

    result = run_ccdata_aggregate_gap_backfill(
        symbols=_split_symbols(args.symbols),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        context_hours=args.context_hours,
        request_pause_seconds=args.request_pause_seconds,
    )
    print(
        "CCData aggregate gap backfill complete: "
        f"gaps_seen={result.gaps_seen} fetched={result.fetched} written={result.written} "
        f"skipped_existing={result.skipped_existing} missing_from_proxy={result.missing_from_proxy} "
        f"run_id={result.run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Sequence

from astro_abm.market_data.binance_derivatives import (
    BinanceFuturesDataClient,
    build_funding_feature_rows,
    build_open_interest_feature_rows,
)
from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.storage.questdb import (
    QuestDBHourlyFactWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class DerivativesBackfillSummary:
    fetched: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]


def run_binance_derivatives_backfill(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    include_open_interest: bool = True,
    client: BinanceFuturesDataClient | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
) -> DerivativesBackfillSummary:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    client = client or BinanceFuturesDataClient()
    writer = writer or QuestDBHourlyFactWriter()
    connection_factory = writer.connection_factory
    fetched = 0
    written = 0
    skipped = 0
    errors: list[str] = []

    for symbol in symbol_list:
        try:
            funding_payload = client.fetch_funding_rates(symbol=symbol, start_ts=start_utc, end_ts=end_utc)
            fetched += len(funding_payload)
            funding_rows = build_funding_feature_rows(funding_payload, end_ts=end_utc)
            funding_rows, funding_skipped = _filter_existing(
                funding_rows,
                connection_factory=connection_factory,
                entity_id=symbol,
                metric_name="funding_rate",
                start_utc=start_utc,
                end_utc=end_utc,
            )
            skipped += funding_skipped
            writer.write(funding_rows)
            written += len(funding_rows)
        except Exception as exc:
            errors.append(f"{symbol}:funding:{type(exc).__name__}:{exc}")

        if include_open_interest:
            try:
                oi_start = max(start_utc, datetime.now(UTC) - timedelta(days=30))
                oi_payload = client.fetch_open_interest_history(symbol=symbol, start_ts=oi_start, end_ts=end_utc)
                fetched += len(oi_payload)
                oi_rows = build_open_interest_feature_rows(oi_payload)
                oi_rows, oi_skipped = _filter_existing(
                    oi_rows,
                    connection_factory=connection_factory,
                    entity_id=symbol,
                    metric_name="open_interest",
                    start_utc=oi_start,
                    end_utc=end_utc,
                )
                skipped += oi_skipped
                writer.write(oi_rows)
                written += len(oi_rows)
            except Exception as exc:
                errors.append(f"{symbol}:open_interest:{type(exc).__name__}:{exc}")

    return DerivativesBackfillSummary(fetched=fetched, written=written, skipped_existing=skipped, errors=tuple(errors))


def _filter_existing(rows, *, connection_factory, entity_id: str, metric_name: str, start_utc: datetime, end_utc: datetime):
    existing = load_existing_fact_timestamps(
        connection_factory,
        entity_id=entity_id,
        source="binance_futures",
        metric_name=metric_name,
        start_ts=start_utc,
        end_ts=end_utc + timedelta(hours=1),
    )
    new_rows = [row for row in rows if row["ts"] not in existing]
    return new_rows, len(rows) - len(new_rows)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill Binance futures funding and open-interest features.")
    parser.add_argument("--symbols", default="BTCUSDT", help="Comma-separated symbols.")
    parser.add_argument("--start", default="2019-09-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--no-open-interest", action="store_true", help="Skip open interest. Funding history can go further back.")
    args = parser.parse_args(argv)
    result = run_binance_derivatives_backfill(
        symbols=normalize_symbols(args.symbols.split(",")),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        include_open_interest=not args.no_open_interest,
    )
    print(
        "Binance derivatives backfill complete: "
        f"fetched={result.fetched} written={result.written} "
        f"skipped_existing={result.skipped_existing} errors={len(result.errors)}"
    )
    if result.errors:
        for error in result.errors[:10]:
            print(f"error: {error}")
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Sequence
from uuid import uuid4

from astro_abm.etl.pipeline import normalize_to_utc_hour
from astro_abm.market_data.binance_derivatives import (
    BinanceFuturesDataClient,
    build_current_open_interest_feature_rows,
)
from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class BinanceOpenInterestCollectSummary:
    fetched: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]
    run_id: str


def run_binance_open_interest_collect(
    *,
    symbols: Sequence[str],
    run_ts: datetime,
    client: BinanceFuturesDataClient | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> BinanceOpenInterestCollectSummary:
    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    bucket_ts = normalize_to_utc_hour(run_ts)
    run_id = run_id or f"binance-oi-current-{uuid4().hex}"
    started_at = datetime.now(UTC)
    client = client or BinanceFuturesDataClient()
    writer = writer or QuestDBHourlyFactWriter()
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=writer.connection_factory)

    fetched = 0
    written = 0
    skipped = 0
    errors: list[str] = []

    for symbol in symbol_list:
        try:
            payload = client.fetch_current_open_interest(symbol=symbol)
            fetched += 1
            rows = build_current_open_interest_feature_rows([payload], bucket_ts=bucket_ts)
            existing = load_existing_fact_timestamps(
                writer.connection_factory,
                entity_id=symbol,
                source="binance_futures_current",
                metric_name="open_interest",
                start_ts=bucket_ts,
                end_ts=bucket_ts + timedelta(hours=1),
            )
            new_rows = [{**row, "ingest_run_id": run_id} for row in rows if row["ts"] not in existing]
            skipped += len(rows) - len(new_rows)
            writer.write(new_rows)
            written += len(new_rows)
        except Exception as exc:
            errors.append(f"{symbol}:{type(exc).__name__}:{exc}")

    if record_run:
        status = "success" if not errors else "partial" if written else "failed"
        run_writer.write(
            ETLRunRecord(
                started_at=started_at,
                run_id=run_id,
                job_type="binance_open_interest_collect",
                provider="binance_futures_current",
                window_start=bucket_ts,
                window_end=bucket_ts + timedelta(hours=1),
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes="Forward collection from Binance current open-interest endpoint.",
            )
        )

    return BinanceOpenInterestCollectSummary(
        fetched=fetched,
        written=written,
        skipped_existing=skipped,
        errors=tuple(errors),
        run_id=run_id,
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect current Binance futures open interest into hourly facts.")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="Comma-separated futures symbols.")
    parser.add_argument("--run-ts", default=datetime.now(UTC).isoformat(), help="UTC timestamp to bucket, defaults to now.")
    args = parser.parse_args(argv)
    result = run_binance_open_interest_collect(
        symbols=normalize_symbols(args.symbols.split(",")),
        run_ts=_parse_utc(args.run_ts),
    )
    print(
        "Binance current OI collect complete: "
        f"fetched={result.fetched} written={result.written} "
        f"skipped_existing={result.skipped_existing} errors={len(result.errors)} "
        f"run_id={result.run_id}"
    )
    if result.errors:
        for error in result.errors[:10]:
            print(f"error: {error}")
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

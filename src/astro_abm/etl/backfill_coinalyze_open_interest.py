from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Sequence
from uuid import uuid4

from astro_abm.config import load_market_data_settings
from astro_abm.market_data.coinalyze_derivatives import (
    CoinalyzeDerivativesClient,
    build_coinalyze_open_interest_feature_rows,
    normalize_coinalyze_entity_id,
    parse_coinalyze_open_interest_history,
)
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class CoinalyzeOpenInterestBackfillSummary:
    fetched_points: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]
    run_id: str


def run_coinalyze_open_interest_backfill(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    interval: str = "1hour",
    convert_to_usd: bool = False,
    client: CoinalyzeDerivativesClient | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> CoinalyzeOpenInterestBackfillSummary:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    symbol_list = [symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()]
    if not symbol_list:
        raise ValueError("symbols must contain at least one Coinalyze symbol.")

    settings = load_market_data_settings()
    client = client or CoinalyzeDerivativesClient(api_key=settings.coinalyze_api_key or "")
    writer = writer or QuestDBHourlyFactWriter()
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=writer.connection_factory)
    run_id = run_id or f"coinalyze-oi-{uuid4().hex}"
    started_at = datetime.now(UTC)
    source = _source_for_interval(interval)

    fetched_points = 0
    written = 0
    skipped = 0
    errors: list[str] = []
    try:
        payload = client.fetch_open_interest_history(
            symbols=symbol_list,
            interval=interval,
            start_ts=start_utc,
            end_ts=end_utc,
            convert_to_usd=convert_to_usd,
        )
        points = parse_coinalyze_open_interest_history(payload, convert_to_usd=convert_to_usd)
        fetched_points = len(points)
        rows = build_coinalyze_open_interest_feature_rows(points, source=source)
        rows, skipped = _filter_existing(
            rows,
            symbols=symbol_list,
            source=source,
            connection_factory=writer.connection_factory,
            start_utc=start_utc,
            end_utc=end_utc,
            metric_name="open_interest_value" if convert_to_usd else "open_interest",
        )
        rows = [{**row, "ingest_run_id": run_id, "interval": _interval_label(interval)} for row in rows]
        writer.write(rows)
        written = len(rows)
    except Exception as exc:
        errors.append(f"{type(exc).__name__}:{exc}")

    if record_run:
        status = "success" if not errors else "partial" if written else "failed"
        run_writer.write(
            ETLRunRecord(
                started_at=started_at,
                run_id=run_id,
                job_type="coinalyze_open_interest_backfill",
                provider=source,
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes=f"interval={interval}; convert_to_usd={convert_to_usd}; symbols={','.join(symbol_list)}",
            )
        )

    return CoinalyzeOpenInterestBackfillSummary(
        fetched_points=fetched_points,
        written=written,
        skipped_existing=skipped,
        errors=tuple(errors),
        run_id=run_id,
    )


def _filter_existing(rows, *, symbols: Sequence[str], source: str, connection_factory, start_utc: datetime, end_utc: datetime, metric_name: str):
    existing = set()
    for symbol in symbols:
        existing.update(
            load_existing_fact_timestamps(
                connection_factory,
                entity_id=normalize_coinalyze_entity_id(symbol),
                source=source,
                metric_name=metric_name,
                start_ts=start_utc,
                end_ts=end_utc + timedelta(hours=1),
            )
        )
    new_rows = [row for row in rows if row["ts"] not in existing]
    return new_rows, len(rows) - len(new_rows)


def _source_for_interval(interval: str) -> str:
    if interval == "1hour":
        return "coinalyze_1h"
    if interval == "daily":
        return "coinalyze_daily"
    return "coinalyze"


def _interval_label(interval: str) -> str:
    lookup = {
        "1min": "1m",
        "5min": "5m",
        "15min": "15m",
        "30min": "30m",
        "1hour": "1h",
        "4hour": "4h",
        "daily": "1d",
    }
    return lookup.get(interval, interval)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill open interest from Coinalyze.")
    parser.add_argument("--symbols", default="BTCUSDT_PERP.A,ETHUSDT_PERP.A", help="Comma-separated Coinalyze symbols.")
    parser.add_argument("--start", required=True, help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--interval", default="1hour", help="Coinalyze interval, e.g. 1hour or daily.")
    parser.add_argument("--convert-to-usd", action="store_true", help="Store USD-valued open interest as open_interest_value.")
    args = parser.parse_args(argv)
    result = run_coinalyze_open_interest_backfill(
        symbols=args.symbols.split(","),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        interval=args.interval,
        convert_to_usd=args.convert_to_usd,
    )
    print(
        "Coinalyze OI backfill complete: "
        f"fetched_points={result.fetched_points} written={result.written} "
        f"skipped_existing={result.skipped_existing} errors={len(result.errors)} "
        f"run_id={result.run_id}"
    )
    if result.errors:
        for error in result.errors[:10]:
            print(f"error: {error}")
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Sequence
from uuid import uuid4

import pandas as pd

from astro_abm.features.regime import build_regime_label_rows
from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
)
from astro_abm.etl.build_regime_features import _load_existing_metric_keys, _time_chunks
from astro_abm.etl.build_regime_features import _normalize_frame_timestamps


@dataclass(frozen=True)
class RegimeLabelBuildResult:
    read_rows: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...] = ()
    run_id: str = ""


def run_regime_label_build(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    horizon_hours: int = 24,
    chunk_days: int = 90,
    connection_factory: Callable | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> RegimeLabelBuildResult:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    if horizon_hours <= 0:
        raise ValueError("horizon_hours must be greater than 0.")
    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    writer = writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=connection_factory)
    run_id = run_id or f"regime-labels-{uuid4().hex}"
    started_at = datetime.now(UTC)
    read_rows = 0
    written = 0
    skipped = 0
    errors: list[str] = []

    for symbol in symbol_list:
        for chunk_start, chunk_end in _time_chunks(start_utc, end_utc, chunk_days=chunk_days):
            try:
                query_end = chunk_end + timedelta(hours=horizon_hours)
                frame = _load_price_frame(
                    connection_factory,
                    symbol=symbol,
                    start_utc=chunk_start,
                    end_utc=query_end,
                )
                read_rows += len(frame)
                if frame.empty:
                    continue

                rows = [
                    {**row, "ingest_run_id": run_id}
                    for row in build_regime_label_rows(frame)
                    if chunk_start <= row["ts"] < chunk_end
                ]
                existing = _load_existing_metric_keys(
                    connection_factory,
                    entity_id=symbol,
                    source="regime_labels",
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
                job_type="regime_label_build",
                provider="regime_labels",
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes=f"Built forward regime labels. horizon_hours={horizon_hours}.",
            )
        )

    return RegimeLabelBuildResult(
        read_rows=read_rows,
        written=written,
        skipped_existing=skipped,
        errors=tuple(errors),
        run_id=run_id,
    )


def _load_price_frame(connection_factory: Callable, *, symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    sql = """
    SELECT ts, symbol, close, volume, data_quality, is_proxy_data
    FROM v_market_ohlcv_ml_1h
    WHERE symbol = %s
      AND ts >= %s
      AND ts < %s
    ORDER BY ts
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (symbol, start_utc, end_utc))
            frame = pd.DataFrame(cursor.fetchall(), columns=["ts", "symbol", "close", "volume", "data_quality", "is_proxy_data"])
    return _normalize_frame_timestamps(frame)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build forward regime labels from ML market bars.")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="Comma-separated symbols.")
    parser.add_argument("--start", default="2017-01-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--horizon-hours", type=int, default=24, help="Forward label horizon in hours.")
    parser.add_argument("--chunk-days", type=int, default=90, help="Query/write chunk size in days.")
    args = parser.parse_args(argv)
    result = run_regime_label_build(
        symbols=normalize_symbols(args.symbols.split(",")),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        horizon_hours=args.horizon_hours,
        chunk_days=args.chunk_days,
    )
    print(
        "Regime label build complete: "
        f"read_rows={result.read_rows} written={result.written} skipped_existing={result.skipped_existing} "
        f"errors={len(result.errors)} run_id={result.run_id}"
    )
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

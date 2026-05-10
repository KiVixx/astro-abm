from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Sequence
from uuid import uuid4

from astro_abm.etl.pipeline import normalize_to_utc_hour
from astro_abm.features.ephemeris import EPHEMERIS_FEATURE_METRICS, EphemerisCalculator, build_ephemeris_feature_rows
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
)


@dataclass(frozen=True)
class EphemerisBackfillSummary:
    hours_seen: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]
    run_id: str


def run_ephemeris_backfill(
    *,
    start_utc: datetime,
    end_utc: datetime,
    chunk_days: int = 90,
    calculator: Any | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    connection_factory: Callable | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> EphemerisBackfillSummary:
    start_utc = normalize_to_utc_hour(start_utc)
    end_utc = normalize_to_utc_hour(end_utc)
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    if chunk_days <= 0:
        raise ValueError("chunk_days must be greater than 0.")

    run_id = run_id or f"ephemeris-{uuid4().hex}"
    started_at = datetime.now(UTC)
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    writer = writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=connection_factory)
    calculator = calculator or EphemerisCalculator()

    hours_seen = 0
    written = 0
    skipped = 0
    errors: list[str] = []

    for chunk_start, chunk_end in _time_chunks(start_utc, end_utc, chunk_days=chunk_days):
        existing = _load_existing_ephemeris_keys(
            connection_factory,
            start_ts=chunk_start,
            end_ts=chunk_end,
        )
        rows = []
        expected_metrics = set(EPHEMERIS_FEATURE_METRICS)
        for ts in _hourly_range(chunk_start, chunk_end):
            hours_seen += 1
            existing_metrics = {metric_name for existing_ts, metric_name in existing if existing_ts == ts}
            if expected_metrics.issubset(existing_metrics):
                skipped += len(expected_metrics)
                continue
            try:
                features = calculator.compute_features(ts)
            except Exception as exc:
                errors.append(f"{ts.isoformat()}:{type(exc).__name__}:{exc}")
                continue
            feature_rows = [
                {**row, "ingest_run_id": run_id}
                for row in build_ephemeris_feature_rows(ts=ts, features=features)
            ]
            new_rows = [row for row in feature_rows if (row["ts"], row["metric_name"]) not in existing]
            skipped += len(feature_rows) - len(new_rows)
            rows.extend(new_rows)

        writer.write(rows)
        written += len(rows)

    summary = EphemerisBackfillSummary(
        hours_seen=hours_seen,
        written=written,
        skipped_existing=skipped,
        errors=tuple(errors),
        run_id=run_id,
    )
    if record_run:
        status = "success" if not errors else "partial"
        run_writer.write(
            ETLRunRecord(
                started_at=started_at,
                run_id=run_id,
                job_type="ephemeris_backfill",
                provider="pyswisseph",
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes="Hourly local Swiss Ephemeris derived features.",
            )
        )
    return summary


def _time_chunks(start_utc: datetime, end_utc: datetime, *, chunk_days: int):
    current = start_utc
    step = timedelta(days=chunk_days)
    while current < end_utc:
        next_end = min(end_utc, current + step)
        yield current, next_end
        current = next_end


def _hourly_range(start_utc: datetime, end_utc: datetime):
    current = start_utc
    while current < end_utc:
        yield current
        current += timedelta(hours=1)


def _load_existing_ephemeris_keys(connection_factory: Callable, *, start_ts: datetime, end_ts: datetime) -> set[tuple[datetime, str]]:
    sql = """
    SELECT ts, metric_name
    FROM abm_hourly_facts
    WHERE entity_id = 'GLOBAL'
      AND source = 'pyswisseph'
      AND ts >= %s
      AND ts < %s
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (start_ts, end_ts))
            return {
                (row[0].replace(tzinfo=start_ts.tzinfo) if row[0].tzinfo is None else row[0], row[1])
                for row in cursor.fetchall()
            }


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill hourly Swiss Ephemeris features into QuestDB.")
    parser.add_argument("--start", default="2017-01-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--chunk-days", type=int, default=90, help="Query/write chunk size in days.")
    args = parser.parse_args(argv)
    result = run_ephemeris_backfill(
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        chunk_days=args.chunk_days,
    )
    print(
        "Ephemeris backfill complete: "
        f"hours_seen={result.hours_seen} written={result.written} "
        f"skipped_existing={result.skipped_existing} errors={len(result.errors)} "
        f"run_id={result.run_id}"
    )
    if result.errors:
        for error in result.errors[:10]:
            print(f"error: {error}")
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

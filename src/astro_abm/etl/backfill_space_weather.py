from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Sequence
from uuid import uuid4

from astro_abm.etl.pipeline import normalize_to_utc_hour
from astro_abm.features.nasa_omni import (
    NasaOmniClient,
    build_omni_space_weather_feature_rows,
    parse_omni2_hourly_payload,
)
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class SpaceWeatherBackfillSummary:
    years_seen: int
    records_seen: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]
    run_id: str


def run_space_weather_backfill(
    *,
    start_utc: datetime,
    end_utc: datetime,
    client: Any | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    connection_factory: Callable | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> SpaceWeatherBackfillSummary:
    start_utc = normalize_to_utc_hour(start_utc)
    end_utc = normalize_to_utc_hour(end_utc)
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")

    run_id = run_id or f"space-weather-{uuid4().hex}"
    started_at = datetime.now(UTC)
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    client = client or NasaOmniClient()
    writer = writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=connection_factory)

    written = 0
    skipped = 0
    records_seen = 0
    years_seen = 0
    errors: list[str] = []

    for year in range(start_utc.year, end_utc.year + 1):
        window_start = max(start_utc, datetime(year, 1, 1, tzinfo=UTC))
        window_end = min(end_utc, datetime(year + 1, 1, 1, tzinfo=UTC))
        if window_end <= window_start:
            continue
        years_seen += 1
        try:
            payload = client.fetch_year(year)
            records = parse_omni2_hourly_payload(payload)
            records_seen += len(records)
            rows = build_omni_space_weather_feature_rows(records, start_utc=window_start, end_utc=window_end)
            rows = [{**row, "ingest_run_id": run_id} for row in rows]
            rows, year_skipped = _filter_existing(
                rows,
                connection_factory=connection_factory,
                start_utc=window_start,
                end_utc=window_end,
            )
            skipped += year_skipped
            writer.write(rows)
            written += len(rows)
        except Exception as exc:
            errors.append(f"{year}:{type(exc).__name__}:{exc}")

    summary = SpaceWeatherBackfillSummary(
        years_seen=years_seen,
        records_seen=records_seen,
        written=written,
        skipped_existing=skipped,
        errors=tuple(errors),
        run_id=run_id,
    )
    if record_run:
        status = "success" if not errors else "partial" if written else "failed"
        run_writer.write(
            ETLRunRecord(
                started_at=started_at,
                run_id=run_id,
                job_type="space_weather_backfill",
                provider="nasa_omni",
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes="Hourly OMNI solar wind speed, IMF Bz, and Kp. Kp is a 3-hour planetary index represented on hourly buckets.",
            )
        )
    return summary


def _filter_existing(rows, *, connection_factory, start_utc: datetime, end_utc: datetime):
    existing_by_metric = {
        metric_name: load_existing_fact_timestamps(
            connection_factory,
            entity_id="GLOBAL",
            source="nasa_omni",
            metric_name=metric_name,
            start_ts=start_utc,
            end_ts=end_utc,
        )
        for metric_name in ("solar_wind_speed", "imf_bz", "kp_index")
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
    parser = argparse.ArgumentParser(description="Backfill historical OMNI space-weather features into QuestDB.")
    parser.add_argument("--start", default="2017-01-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    args = parser.parse_args(argv)
    result = run_space_weather_backfill(start_utc=_parse_utc(args.start), end_utc=_parse_utc(args.end))
    print(
        "Space-weather backfill complete: "
        f"years_seen={result.years_seen} records_seen={result.records_seen} "
        f"written={result.written} skipped_existing={result.skipped_existing} "
        f"errors={len(result.errors)} run_id={result.run_id}"
    )
    if result.errors:
        for error in result.errors[:10]:
            print(f"error: {error}")
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

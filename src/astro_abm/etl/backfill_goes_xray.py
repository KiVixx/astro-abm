from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import uuid4

from astro_abm.etl.pipeline import normalize_to_utc_hour
from astro_abm.features.goes_xray import (
    GoesXrayClient,
    build_goes_xray_feature_rows,
    read_goes_xray_hourly_records,
    select_goes_xray_satellite,
)
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class GoesXrayBackfillSummary:
    years_seen: int
    records_seen: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]
    run_id: str


def run_goes_xray_backfill(
    *,
    start_utc: datetime,
    end_utc: datetime,
    cache_dir: Path | None = None,
    client: Any | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    connection_factory: Callable | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> GoesXrayBackfillSummary:
    start_utc = normalize_to_utc_hour(start_utc)
    end_utc = normalize_to_utc_hour(end_utc)
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")

    run_id = run_id or f"goes-xray-{uuid4().hex}"
    started_at = datetime.now(UTC)
    cache_dir = cache_dir or Path.home() / ".cache" / "astro-abm" / "goes-xray"
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    client = client or GoesXrayClient()
    writer = writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=connection_factory)

    years_seen = 0
    records_seen = 0
    written = 0
    skipped = 0
    errors: list[str] = []
    archive_unavailable_detail: str | None = None

    for year in range(start_utc.year, end_utc.year + 1):
        window_start = max(start_utc, datetime(year, 1, 1, tzinfo=UTC))
        window_end = min(end_utc, datetime(year + 1, 1, 1, tzinfo=UTC))
        if window_end <= window_start:
            continue
        years_seen += 1
        satellite = select_goes_xray_satellite(year)
        try:
            cached = _client_year_cached(client, year=year, satellite=satellite, cache_dir=cache_dir)
            if not cached:
                if archive_unavailable_detail is None:
                    ok, detail = _client_archive_healthcheck(client)
                    if not ok:
                        archive_unavailable_detail = detail
                if archive_unavailable_detail:
                    errors.append(f"{year}:{satellite}:SourceUnavailable:{archive_unavailable_detail}")
                    continue
            path = client.download_year(year=year, satellite=satellite, cache_dir=cache_dir)
            records = read_goes_xray_hourly_records(path, start_utc=window_start, end_utc=window_end, satellite=satellite)
            records_seen += len(records)
            rows = [{**row, "ingest_run_id": run_id} for row in build_goes_xray_feature_rows(records)]
            existing = load_existing_fact_timestamps(
                connection_factory,
                entity_id="GLOBAL",
                source="noaa_goes_xrs",
                metric_name="xray_flux",
                start_ts=window_start,
                end_ts=window_end,
            )
            new_rows = [row for row in rows if row["ts"] not in existing]
            skipped += len(rows) - len(new_rows)
            writer.write(new_rows)
            written += len(new_rows)
        except Exception as exc:
            errors.append(f"{year}:{satellite}:{type(exc).__name__}:{exc}")

    summary = GoesXrayBackfillSummary(
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
                job_type="goes_xray_backfill",
                provider="noaa_goes_xrs",
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes="Hourly mean of GOES-R XRS-B primary 1-minute flux. metric_value_2 stores sample count.",
            )
        )
    return summary


def _client_year_cached(client: Any, *, year: int, satellite: str, cache_dir: Path) -> bool:
    checker = getattr(client, "is_year_cached", None)
    if checker is None:
        return False
    return bool(checker(year=year, satellite=satellite, cache_dir=cache_dir))


def _client_archive_healthcheck(client: Any) -> tuple[bool, str]:
    checker = getattr(client, "archive_healthcheck", None)
    if checker is None:
        return True, "unsupported"
    return checker()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill historical GOES XRS X-ray flux into QuestDB.")
    parser.add_argument("--start", default="2017-01-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--cache-dir", default=None, help="Directory for downloaded yearly netCDF files.")
    args = parser.parse_args(argv)
    result = run_goes_xray_backfill(
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )
    print(
        "GOES X-ray backfill complete: "
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

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Iterable, Sequence
from uuid import uuid4

from astro_abm.etl.pipeline import normalize_to_utc_hour
from astro_abm.features.space_weather import SpaceWeatherClient, build_space_weather_feature_rows
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
    load_existing_fact_timestamps,
)


@dataclass(frozen=True)
class NoaaSwpcRecentBackfillSummary:
    hours_seen: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]
    run_id: str


def run_noaa_swpc_recent_backfill(
    *,
    start_utc: datetime,
    end_utc: datetime,
    client: Any | None = None,
    writer: QuestDBHourlyFactWriter | None = None,
    run_writer: QuestDBETLRunWriter | None = None,
    connection_factory: Callable | None = None,
    run_id: str | None = None,
    record_run: bool = True,
) -> NoaaSwpcRecentBackfillSummary:
    start_utc = normalize_to_utc_hour(start_utc)
    end_utc = normalize_to_utc_hour(end_utc)
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")

    run_id = run_id or f"noaa-swpc-recent-{uuid4().hex}"
    started_at = datetime.now(UTC)
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    client = client or SpaceWeatherClient()
    writer = writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=connection_factory)

    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    hours_seen = 0
    try:
        plasma_rows = client.fetch_plasma()
        mag_rows = client.fetch_magnetometer()
        xray_rows = client.fetch_xray_flux()
        kp_rows = client.fetch_hourly_kp()
        for bucket_ts in _hourly_range(start_utc, end_utc):
            hours_seen += 1
            snapshot = _build_hourly_snapshot(
                bucket_ts=bucket_ts,
                plasma_rows=plasma_rows,
                mag_rows=mag_rows,
                xray_rows=xray_rows,
                kp_rows=kp_rows,
            )
            if snapshot is None:
                continue
            rows.extend({**row, "ingest_run_id": run_id} for row in snapshot)
    except Exception as exc:
        errors.append(f"fetch:{type(exc).__name__}:{exc}")

    rows, skipped = _filter_existing(rows, connection_factory=connection_factory, start_utc=start_utc, end_utc=end_utc)
    writer.write(rows)
    written = len(rows)

    summary = NoaaSwpcRecentBackfillSummary(
        hours_seen=hours_seen,
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
                job_type="noaa_swpc_recent_backfill",
                provider="noaa_swpc_recent",
                window_start=start_utc,
                window_end=end_utc,
                status=status,
                rows_written=written,
                skipped_existing=skipped,
                errors=len(errors),
                finished_at=datetime.now(UTC),
                notes="Provisional SWPC recent feed. No interpolation or forward-fill beyond latest observed source samples.",
            )
        )
    return summary


def _build_hourly_snapshot(
    *,
    bucket_ts: datetime,
    plasma_rows: Iterable[dict[str, Any]],
    mag_rows: Iterable[dict[str, Any]],
    xray_rows: Iterable[dict[str, Any]],
    kp_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    plasma = _latest_before(plasma_rows, "time_tag", bucket_ts)
    mag = _latest_before(mag_rows, "time_tag", bucket_ts)
    xray = _latest_before(xray_rows, "time_tag", bucket_ts)
    kp = _latest_before(kp_rows, "ts", bucket_ts)
    if not all([plasma, mag, xray, kp]):
        return None

    observed_ts = max(plasma["time_tag"], mag["time_tag"], xray["time_tag"], kp["ts"])
    return build_space_weather_feature_rows(
        ts=bucket_ts,
        solar_wind_speed=float(plasma["speed"]),
        imf_bz=float(mag["bz_gsm"]),
        xray_flux=float(xray["flux"]),
        kp_index=float(kp["kp_index"]),
        observed_ts=observed_ts,
        available_ts=datetime.now(UTC),
        source="noaa_swpc_recent",
        quality_flag="provisional",
    )


def _filter_existing(rows, *, connection_factory, start_utc: datetime, end_utc: datetime):
    existing_by_metric = {
        metric_name: load_existing_fact_timestamps(
            connection_factory,
            entity_id="GLOBAL",
            source="noaa_swpc_recent",
            metric_name=metric_name,
            start_ts=start_utc,
            end_ts=end_utc,
        )
        for metric_name in ("solar_wind_speed", "imf_bz", "xray_flux", "kp_index")
    }
    new_rows = [
        row
        for row in rows
        if row["ts"] not in existing_by_metric.get(row["metric_name"], set())
    ]
    return new_rows, len(rows) - len(new_rows)


def _latest_before(rows: Iterable[dict[str, Any]], timestamp_key: str, bucket_ts: datetime) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get(timestamp_key) is not None and row[timestamp_key] <= bucket_ts]
    if not candidates:
        return None
    return max(candidates, key=lambda row: row[timestamp_key])


def _hourly_range(start_utc: datetime, end_utc: datetime):
    current = start_utc
    while current < end_utc:
        yield current
        current += timedelta(hours=1)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill provisional NOAA SWPC recent space-weather features.")
    parser.add_argument("--start", default=(datetime.now(UTC) - timedelta(days=1)).isoformat(), help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    args = parser.parse_args(argv)
    result = run_noaa_swpc_recent_backfill(start_utc=_parse_utc(args.start), end_utc=_parse_utc(args.end))
    print(
        "NOAA SWPC recent backfill complete: "
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

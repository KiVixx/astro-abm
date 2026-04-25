from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Sequence
from uuid import uuid4

from astro_abm.config import load_market_data_settings
from astro_abm.etl.pipeline import normalize_to_utc_hour
from astro_abm.features.social_sentiment import AskGrokSentimentClient
from astro_abm.storage.questdb import (
    ETLRunRecord,
    QuestDBETLRunWriter,
    QuestDBHourlyFactWriter,
    QuestDBMarketBarWriter,
    askgrok_fact_exists,
)


@dataclass(frozen=True)
class AskGrokBackfillResult:
    run_id: str
    window_start: datetime
    window_end: datetime
    attempted_hours: int
    rows_written: int
    skipped_existing: int
    errors: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.errors and self.rows_written == 0:
            return "failed"
        if self.errors:
            return "partial"
        return "success"


def run_askgrok_backfill(
    *,
    start_utc: datetime,
    end_utc: datetime,
    assets: Sequence[str],
    max_hours: int = 24,
    skip_existing: bool = True,
    client: Any | None = None,
    fact_writer: Any | None = None,
    run_writer: Any | None = None,
    connection_factory: Callable | None = None,
) -> AskGrokBackfillResult:
    if max_hours <= 0:
        raise ValueError("max_hours must be greater than 0.")
    if max_hours > 168:
        raise ValueError("max_hours is capped at 168 for controlled ASKGROK backfills.")

    window_start = normalize_to_utc_hour(start_utc)
    window_end = normalize_to_utc_hour(end_utc)
    if window_end <= window_start:
        raise ValueError("end_utc must be after start_utc.")

    asset_list = [asset.strip().upper() for asset in assets if asset and asset.strip()]
    if not asset_list:
        raise ValueError("assets must contain at least one symbol.")

    run_id = f"askgrok-{uuid4().hex}"
    started_at = datetime.now(UTC)
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    client = client or _build_default_askgrok_client()
    fact_writer = fact_writer or QuestDBHourlyFactWriter(connection_factory=connection_factory)
    run_writer = run_writer or QuestDBETLRunWriter(connection_factory=connection_factory)

    rows_written = 0
    skipped_existing = 0
    errors: list[str] = []
    attempted_hours = 0
    entity_id = ",".join(asset_list)

    for start, end in _hourly_windows(window_start, window_end, max_hours=max_hours):
        attempted_hours += 1
        if skip_existing and askgrok_fact_exists(connection_factory, start, entity_id):
            skipped_existing += 1
            continue

        try:
            rows = client.fetch_feature_rows(start_utc=start, end_utc=end, assets=asset_list)
            rows = [{**row, "ingest_run_id": run_id} for row in rows]
            fact_writer.write(rows)
            rows_written += len(rows)
        except Exception as exc:
            errors.append(f"{start.isoformat()}:{type(exc).__name__}:{exc}")

    result = AskGrokBackfillResult(
        run_id=run_id,
        window_start=window_start,
        window_end=min(window_end, window_start + timedelta(hours=max_hours)),
        attempted_hours=attempted_hours,
        rows_written=rows_written,
        skipped_existing=skipped_existing,
        errors=tuple(errors),
    )
    run_writer.write(
        ETLRunRecord(
            started_at=started_at,
            run_id=run_id,
            job_type="askgrok_backfill",
            provider="ASKGROK_WEB",
            window_start=result.window_start,
            window_end=result.window_end,
            status=result.status,
            rows_written=result.rows_written,
            skipped_existing=result.skipped_existing,
            errors=len(result.errors),
            finished_at=datetime.now(UTC),
            notes=" | ".join(result.errors[:5]),
        )
    )
    return result


def _build_default_askgrok_client() -> AskGrokSentimentClient:
    settings = load_market_data_settings()
    return AskGrokSentimentClient(
        base_url=settings.askgrok_base_url,
        timeout_ms=settings.askgrok_timeout_ms,
    )


def _hourly_windows(start_utc: datetime, end_utc: datetime, *, max_hours: int):
    current = start_utc
    emitted = 0
    while current < end_utc and emitted < max_hours:
        next_hour = current + timedelta(hours=1)
        yield current, next_hour
        current = next_hour
        emitted += 1


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _split_assets(value: str) -> tuple[str, ...]:
    return tuple(asset.strip().upper() for asset in value.split(",") if asset.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill ASKGROK sentiment in controlled hourly windows.")
    parser.add_argument("--start", required=True, help="UTC start timestamp, inclusive.")
    parser.add_argument("--end", required=True, help="UTC end timestamp, exclusive.")
    parser.add_argument("--assets", default="BTC", help="Comma-separated crypto symbols, e.g. BTC,ETH,LUNA,UST.")
    parser.add_argument("--max-hours", type=int, default=24, help="Safety cap for this run. Max: 168.")
    parser.add_argument("--no-skip-existing", action="store_true", help="Ask ASKGROK even if rows already exist.")
    args = parser.parse_args(argv)

    result = run_askgrok_backfill(
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        assets=_split_assets(args.assets),
        max_hours=args.max_hours,
        skip_existing=not args.no_skip_existing,
    )
    print(
        "ASKGROK backfill complete: "
        f"run_id={result.run_id} "
        f"status={result.status} "
        f"attempted_hours={result.attempted_hours} "
        f"rows_written={result.rows_written} "
        f"skipped_existing={result.skipped_existing} "
        f"errors={len(result.errors)}"
    )
    return 0 if result.status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

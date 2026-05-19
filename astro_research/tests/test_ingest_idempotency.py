from pathlib import Path

import pandas as pd


def test_daily_migrations_use_year_wal_and_dedup_keys():
    root = Path(__file__).resolve().parents[1]
    sql = "\n".join(path.read_text() for path in sorted((root / "migrations").glob("*.sql")))

    assert "PARTITION BY YEAR WAL" in sql
    assert "DEDUP UPSERT KEYS(ts, dataset_id, body)" in sql
    assert "DEDUP UPSERT KEYS(ts, dataset_id)" in sql
    assert "DEDUP UPSERT KEYS(station_in_ts, dataset_id, cycle_id)" in sql


def test_ingest_filter_drops_pre_1970_designated_timestamps():
    from astro_daily.ingest_questdb import _filter_min_timestamp

    frame = pd.DataFrame(
        [
            {"ts": "1929-10-24T00:00:00Z", "dataset_id": "astro_daily_v1_swe_utc00"},
            {"ts": "1970-01-01T00:00:00Z", "dataset_id": "astro_daily_v1_swe_utc00"},
            {"ts": "2025-12-31T00:00:00Z", "dataset_id": "astro_daily_v1_swe_utc00"},
        ]
    )

    filtered = _filter_min_timestamp(frame, table="astro_daily_features", min_ts="1970-01-01T00:00:00Z")

    assert filtered["ts"].tolist() == ["1970-01-01T00:00:00Z", "2025-12-31T00:00:00Z"]

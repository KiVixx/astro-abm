from pathlib import Path


def test_daily_migrations_use_year_wal_and_dedup_keys():
    root = Path(__file__).resolve().parents[1]
    sql = "\n".join(path.read_text() for path in sorted((root / "migrations").glob("*.sql")))

    assert "PARTITION BY YEAR WAL" in sql
    assert "DEDUP UPSERT KEYS(ts, dataset_id, body)" in sql
    assert "DEDUP UPSERT KEYS(ts, dataset_id)" in sql
    assert "DEDUP UPSERT KEYS(station_in_ts, dataset_id, cycle_id)" in sql

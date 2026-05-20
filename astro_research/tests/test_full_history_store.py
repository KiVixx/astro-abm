from __future__ import annotations

import duckdb
import pandas as pd

from research.full_history_store import build_duckdb_store, discover_snapshot_sources


def test_duckdb_store_preserves_pre_1970_daily_rows(tmp_path):
    snapshot_root = tmp_path / "parquet"
    daily_dir = snapshot_root / "astro_daily_1926_2025"
    daily_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "ts": ["1926-01-01 00:00:00+00:00", "1970-01-01 00:00:00+00:00"],
            "dataset_id": ["astro_daily_v1_swe_utc00", "astro_daily_v1_swe_utc00"],
            "active_retrograde_count": [2, 1],
        }
    ).to_csv(daily_dir / "astro_daily_features.csv", index=False)

    result = build_duckdb_store(snapshot_root=snapshot_root, output_path=tmp_path / "research.duckdb")

    with duckdb.connect(str(result.output_path)) as connection:
        row_count = connection.execute("SELECT count() FROM astro_daily_features").fetchone()[0]
        manifest = connection.execute(
            "SELECT row_count, min_ts, pre_1970_rows, includes_pre_1970 FROM research_store_manifest WHERE table_name='astro_daily_features'"
        ).fetchone()

    assert row_count == 2
    assert manifest == (2, pd.Timestamp("1926-01-01").to_pydatetime(), 1, True)


def test_discovery_prefers_parquet_over_csv(tmp_path):
    snapshot_root = tmp_path / "parquet"
    market_dir = snapshot_root / "market_daily"
    market_dir.mkdir(parents=True)
    frame = pd.DataFrame({"ts": [pd.Timestamp("2020-01-01", tz="UTC")], "asset": ["BTC"], "source": ["fred"]})
    frame.to_csv(market_dir / "market_daily_features.csv", index=False)
    frame.to_parquet(market_dir / "market_daily_features.parquet", index=False)

    sources = discover_snapshot_sources(snapshot_root)
    source = next(item for item in sources if item.table_name == "market_daily_features")

    assert source.source_format == "parquet"
    assert source.paths == (market_dir / "market_daily_features.parquet",)

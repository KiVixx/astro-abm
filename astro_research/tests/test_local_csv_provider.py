from __future__ import annotations

from datetime import date

import pandas as pd

from market_daily.config import AssetConfig, MarketDailyConfig
from market_daily.build import build_market_daily_dataset
from market_daily.providers.local_csv import LocalCSVProvider
from research.source_registry import build_source_registry


def test_local_csv_provider_price_schema(tmp_path):
    path = tmp_path / "spx.csv"
    path.write_text("date,open,high,low,close,adj_close,volume\n2020-01-02,1,2,1,2,2,10\n")
    provider = LocalCSVProvider(root=tmp_path)
    asset = AssetConfig(asset="SPX", source="local_csv", symbol="SPX", timezone="UTC", start_date=date(2020, 1, 1), currency="USD", path="spx.csv")

    frame = provider.fetch_daily_bars(asset=asset, start=date(2020, 1, 1), end=date(2020, 1, 3))

    assert len(frame) == 1
    assert frame.loc[0, "close"] == 2
    assert frame.loc[0, "asset"] == "SPX"


def test_local_csv_provider_indicator_schema(tmp_path):
    path = tmp_path / "hy.csv"
    path.write_text("date,value\n2020-01-02,3.4\n")
    provider = LocalCSVProvider(root=tmp_path)

    frame = provider.fetch_indicator_observations(series_id="BAMLH0A0HYM2", path="hy.csv", start=date(2020, 1, 1), end=date(2020, 1, 3))

    assert len(frame) == 1
    assert frame.loc[0, "value"] == 3.4
    assert frame.loc[0, "series_id"] == "BAMLH0A0HYM2"


def test_local_csv_missing_file_graceful_skip(tmp_path):
    provider = LocalCSVProvider(root=tmp_path)
    asset = AssetConfig(asset="Gold", source="local_csv", symbol="Gold", timezone="UTC", start_date=date(2020, 1, 1), currency="USD", path="missing.csv")

    frame = provider.fetch_daily_bars(asset=asset, start=date(2020, 1, 1), end=date(2020, 1, 3))

    assert frame.empty
    assert "missing file" in frame.attrs["warnings"][0]


def test_local_csv_duplicate_date_detection(tmp_path):
    path = tmp_path / "spx.csv"
    path.write_text("date,close\n2020-01-02,1\n2020-01-02,2\n")
    provider = LocalCSVProvider(root=tmp_path)
    asset = AssetConfig(asset="SPX", source="local_csv", symbol="SPX", timezone="UTC", start_date=date(2020, 1, 1), currency="USD", path="spx.csv")

    frame = provider.fetch_daily_bars(asset=asset, start=date(2020, 1, 1), end=date(2020, 1, 3))

    assert len(frame) == 1
    assert frame.loc[0, "close"] == 2
    assert any("duplicate date" in warning for warning in frame.attrs["warnings"])


def test_market_fallback_priority(tmp_path):
    path = tmp_path / "spx.csv"
    path.write_text("date,close\n2020-01-02,2\n")
    config = MarketDailyConfig(
        data_version="test",
        providers={"fred": {"api_key_env": "MISSING_FRED_API_KEY_FOR_TEST"}},
        assets={
            "SPX": AssetConfig(
                asset="SPX",
                source="fred",
                symbol="SP500",
                timezone="UTC",
                start_date=date(2020, 1, 1),
                currency="USD",
                fallback_source="local_csv",
                fallback_path=str(path),
            )
        },
    )

    bars, features = build_market_daily_dataset(config, root=tmp_path, start=date(2020, 1, 1), end=date(2020, 1, 3))

    assert len(bars) == 1
    assert bars.loc[0, "source"] == "local_csv"
    assert len(features) == 1


def test_local_csv_source_registry_integration():
    registry = build_source_registry("astro_research/configs/data_sources.yaml")
    local = registry.rows[registry.rows["source"] == "local_csv"]

    assert not local.empty
    assert local["license_note"].astype(str).str.len().gt(0).all()
    assert any(local["source_url"].astype(str).str.contains("astro_research/data/local|unavailable_local_file", regex=True))

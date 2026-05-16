from __future__ import annotations

import numpy as np
import pandas as pd

from market_daily.features import build_market_daily_features
from research.stress_features import build_financial_stress, prior_rolling_percentile


def test_rolling_percentile_no_future_leakage():
    series = pd.Series([1.0] * 30 + [100.0])
    percentile = prior_rolling_percentile(series, window=30)

    assert percentile.iloc[-1] == 1.0


def test_financial_stress_score_range(tmp_path):
    dates = pd.date_range("2020-01-01", periods=320, freq="D", tz="UTC")
    prices = 100 * np.exp(np.cumsum(np.r_[np.zeros(300), np.repeat(-0.02, 20)]))
    bars = pd.DataFrame({"ts": dates, "asset": "SPX", "source": "synthetic", "adj_close": prices, "close": prices})
    features = build_market_daily_features(bars, data_version="test")
    market_path = tmp_path / "market.parquet"
    macro_path = tmp_path / "macro.parquet"
    features.to_parquet(market_path)
    pd.DataFrame(
        {
            "ts": dates,
            "series_id": "VIXCLS",
            "source": "fred",
            "value": np.r_[np.repeat(15.0, 300), np.repeat(45.0, 20)],
            "original_frequency": "daily",
            "fill_method": "none",
            "units": "index",
            "data_version": "test",
            "source_note": "test",
        }
    ).to_parquet(macro_path)
    config_path = tmp_path / "stress.yaml"
    config_path.write_text(
        f'''dataset:
  data_version: "test"
  stress_universe: "test"
inputs:
  market_features_path: "{market_path}"
  macro_observations_path: "{macro_path}"
thresholds:
  min_components: 1
'''
    )

    result = build_financial_stress(config_path)

    assert result.frame["cross_asset_stress_score"].dropna().between(0, 1).all()
    assert result.frame["stress_regime"].isin(["stress", "normal", "insufficient_coverage"]).all()


def test_missing_credit_stress_does_not_crash_and_cross_asset_ignores_component(tmp_path):
    dates = pd.date_range("2020-01-01", periods=320, freq="D", tz="UTC")
    prices = 100 * np.exp(np.cumsum(np.r_[np.zeros(300), np.repeat(-0.01, 20)]))
    market = build_market_daily_features(
        pd.DataFrame({"ts": dates, "asset": "SPX", "source": "synthetic", "adj_close": prices, "close": prices}),
        data_version="test",
    )
    macro = pd.DataFrame(
        {
            "ts": dates,
            "series_id": "VIXCLS",
            "source": "fred",
            "value": 20.0,
            "original_frequency": "daily",
            "fill_method": "none",
            "units": "index",
            "data_version": "test",
            "source_note": "test",
        }
    )
    market_path = tmp_path / "market.parquet"
    macro_path = tmp_path / "macro.parquet"
    market.to_parquet(market_path)
    macro.to_parquet(macro_path)
    config_path = tmp_path / "stress.yaml"
    config_path.write_text(
        f'''dataset:
  data_version: "test"
  stress_universe: "test"
inputs:
  market_features_path: "{market_path}"
  macro_observations_path: "{macro_path}"
thresholds:
  min_components: 1
'''
    )

    result = build_financial_stress(config_path)

    assert result.frame["credit_stress_score"].isna().all()
    assert result.frame["cross_asset_stress_score"].notna().any()
    assert "credit_stress_component_missing" in result.warnings


def test_financial_stress_activates_dollar_credit_with_local_like_data(tmp_path):
    dates = pd.date_range("2020-01-01", periods=320, freq="D", tz="UTC")
    dxy_prices = 100 * np.exp(np.cumsum(np.r_[np.zeros(300), np.repeat(0.01, 20)]))
    gold_prices = 1500 * np.exp(np.cumsum(np.r_[np.zeros(300), np.repeat(0.005, 20)]))
    market_rows = []
    for asset, prices in (("DXY", dxy_prices), ("Gold", gold_prices)):
        market_rows.append(pd.DataFrame({"ts": dates, "asset": asset, "source": "local_csv", "adj_close": prices, "close": prices}))
    market = build_market_daily_features(pd.concat(market_rows, ignore_index=True), data_version="test")
    macro = pd.DataFrame(
        {
            "ts": dates,
            "series_id": "BAMLH0A0HYM2",
            "source": "local_csv",
            "value": np.r_[np.repeat(3.0, 300), np.repeat(8.0, 20)],
            "original_frequency": "daily",
            "fill_method": "none",
            "units": "percent",
            "data_version": "test",
            "source_note": "local",
        }
    )
    market_path = tmp_path / "market.parquet"
    macro_path = tmp_path / "macro.parquet"
    market.to_parquet(market_path)
    macro.to_parquet(macro_path)
    config_path = tmp_path / "stress.yaml"
    config_path.write_text(
        f'''dataset:
  data_version: "test"
  stress_universe: "test"
inputs:
  market_features_path: "{market_path}"
  macro_observations_path: "{macro_path}"
thresholds:
  min_components: 1
'''
    )

    result = build_financial_stress(config_path)

    assert result.frame["dollar_stress_score"].notna().any()
    assert result.frame["credit_stress_score"].notna().any()
    assert result.frame["gold_stress_score"].notna().any()

from __future__ import annotations

import math

import pandas as pd

from market_daily.features import build_market_daily_features
from market_daily.normalize import normalize_market_bars


def test_market_return_calculations():
    bars = normalize_market_bars(
        pd.DataFrame(
            {
                "date": ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"],
                "open": [100, 110, 121, 121],
                "high": [100, 110, 121, 121],
                "low": [100, 110, 121, 121],
                "close": [100, 110, 121, 121],
                "volume": [1, 2, 3, 4],
            }
        ),
        asset="BTC",
        source="local_csv",
        currency="USD",
        market_timezone="UTC",
        data_version="v1",
        source_note="test",
    )

    features = build_market_daily_features(bars, data_version="v1")

    assert math.isclose(features.loc[1, "ret_1d"], 0.1)
    assert pd.isna(features.loc[2, "ret_3d"])
    assert math.isclose(features.loc[3, "ret_3d"], 0.21)
    assert math.isclose(features.loc[2, "log_ret_1d"], math.log(121 / 110))


def test_realized_volatility_and_drawdown():
    bars = normalize_market_bars(
        pd.DataFrame(
            {
                "date": pd.date_range("2020-01-01", periods=6, freq="D"),
                "close": [100, 110, 90, 95, 120, 108],
            }
        ),
        asset="BTC",
        source="local_csv",
        currency="USD",
        market_timezone="UTC",
        data_version="v1",
        source_note="test",
    )

    features = build_market_daily_features(bars, data_version="v1")

    assert features["realized_vol_5d"].notna().sum() > 0
    assert features.loc[2, "drawdown_5d"] < 0

from datetime import UTC, datetime

import pandas as pd


def test_build_price_action_feature_rows_computes_hourly_price_metrics():
    from astro_abm.features.price_action import build_price_action_feature_rows

    frame = pd.DataFrame(
        [
            {"ts": datetime(2024, 4, 15, 0, tzinfo=UTC), "symbol": "BTCUSDT", "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 10.0, "market_type": "spot"},
            {"ts": datetime(2024, 4, 15, 1, tzinfo=UTC), "symbol": "BTCUSDT", "open": 105.0, "high": 108.0, "low": 90.0, "close": 95.0, "volume": 30.0, "market_type": "spot"},
            {"ts": datetime(2024, 4, 15, 2, tzinfo=UTC), "symbol": "BTCUSDT", "open": 95.0, "high": 100.0, "low": 94.0, "close": 98.0, "volume": 20.0, "market_type": "spot"},
        ]
    )

    rows = build_price_action_feature_rows(frame)
    second_hour = [row for row in rows if row["ts"] == datetime(2024, 4, 15, 1, tzinfo=UTC)]
    by_metric = {row["metric_name"]: row for row in second_hour}

    assert by_metric["price_return_1h"]["metric_value"] == (95.0 / 105.0) - 1.0
    assert by_metric["price_range_pct"]["metric_value"] == (108.0 - 90.0) / 95.0
    assert by_metric["price_drawdown_24h"]["metric_value"] == (95.0 / 105.0) - 1.0
    assert by_metric["price_return_1h"]["source"] == "price_action"
    assert by_metric["price_return_1h"]["entity_id"] == "BTCUSDT"


def test_price_action_skips_non_numeric_first_hour_return():
    from astro_abm.features.price_action import build_price_action_feature_rows

    frame = pd.DataFrame(
        [
            {"ts": datetime(2024, 4, 15, 0, tzinfo=UTC), "symbol": "ETHUSDT", "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 10.0, "market_type": "spot"},
        ]
    )

    rows = build_price_action_feature_rows(frame)

    assert "price_return_1h" not in {row["metric_name"] for row in rows}
    assert "price_range_pct" in {row["metric_name"] for row in rows}

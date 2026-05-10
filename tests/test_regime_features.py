from datetime import UTC, datetime, timedelta

import pandas as pd


def _frame(hours: int = 220) -> pd.DataFrame:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return pd.DataFrame(
        [
            {
                "ts": start + timedelta(hours=index),
                "symbol": "BTCUSDT",
                "close": 100.0 + index,
                "volume": 10.0 + index,
                "open_interest": 1000.0 + index * 5,
                "funding_rate": 0.0001 + index * 0.000001,
            }
            for index in range(hours)
        ]
    )


def test_build_regime_feature_rows_computes_price_oi_funding_metrics():
    from astro_abm.features.regime import build_regime_feature_rows

    rows = build_regime_feature_rows(_frame())
    by_key = {(row["ts"], row["metric_name"]): row for row in rows}
    ts = datetime(2024, 1, 8, 0, tzinfo=UTC)

    assert by_key[(ts, "regime_return_24h")]["metric_value"] == (268.0 / 244.0) - 1.0
    assert by_key[(ts, "regime_oi_change_24h")]["metric_value"] == ((1000.0 + 168 * 5) / (1000.0 + 144 * 5)) - 1.0
    assert by_key[(ts, "regime_funding_rate")]["metric_value"] == 0.0001 + 168 * 0.000001
    assert by_key[(ts, "regime_return_24h")]["source"] == "regime_features"
    assert by_key[(ts, "regime_return_24h")]["entity_type"] == "regime"
    assert "regime_fragility_score" in {row["metric_name"] for row in rows}


def test_build_regime_label_rows_computes_forward_metrics():
    from astro_abm.features.regime import build_regime_label_rows

    rows = build_regime_label_rows(_frame(80))
    by_key = {(row["ts"], row["metric_name"]): row for row in rows}
    ts = datetime(2024, 1, 2, 0, tzinfo=UTC)

    assert by_key[(ts, "future_return_24h")]["metric_value"] == (148.0 / 124.0) - 1.0
    assert by_key[(ts, "future_abs_return_24h")]["metric_value"] == abs((148.0 / 124.0) - 1.0)
    assert by_key[(ts, "future_drawdown_24h")]["metric_value"] == (125.0 / 124.0) - 1.0
    assert by_key[(ts, "future_return_24h")]["source"] == "regime_labels"
    assert by_key[(ts, "future_return_24h")]["entity_type"] == "regime_label"

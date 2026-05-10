from datetime import UTC, datetime

import pandas as pd


def test_build_training_dataset_pivots_features_labels_and_splits():
    from astro_abm.analysis.training_dataset import build_training_dataset

    price = pd.DataFrame(
        [
            {
                "ts": datetime(2024, 1, 1, 0, tzinfo=UTC),
                "symbol": "BTCUSDT",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 10.0,
                "quote_volume": 1040.0,
                "trade_count": 100,
                "data_quality": "official",
                "is_proxy_data": False,
                "is_imputed": False,
                "volume_scale_ratio": 1.0,
            },
            {
                "ts": datetime(2024, 1, 2, 0, tzinfo=UTC),
                "symbol": "BTCUSDT",
                "open": 104.0,
                "high": 106.0,
                "low": 101.0,
                "close": 102.0,
                "volume": 12.0,
                "quote_volume": 1224.0,
                "trade_count": 120,
                "data_quality": "official",
                "is_proxy_data": False,
                "is_imputed": False,
                "volume_scale_ratio": 1.0,
            },
        ]
    )
    facts = pd.DataFrame(
        [
            {
                "ts": datetime(2024, 1, 1, 0, tzinfo=UTC),
                "symbol": "BTCUSDT",
                "metric_name": "regime_return_24h",
                "metric_value": 0.04,
            },
            {
                "ts": datetime(2024, 1, 1, 0, tzinfo=UTC),
                "symbol": "BTCUSDT",
                "metric_name": "future_return_24h",
                "metric_value": -0.02,
            },
            {
                "ts": datetime(2024, 1, 2, 0, tzinfo=UTC),
                "symbol": "BTCUSDT",
                "metric_name": "regime_return_24h",
                "metric_value": -0.01,
            },
        ]
    )

    dataset = build_training_dataset(
        price,
        facts,
        validation_start=datetime(2024, 1, 2, 0, tzinfo=UTC),
        test_start=datetime(2024, 1, 3, 0, tzinfo=UTC),
    )

    assert len(dataset) == 1
    assert dataset.iloc[0]["future_return_24h"] == -0.02
    assert dataset.iloc[0]["regime_return_24h"] == 0.04
    assert dataset.iloc[0]["split"] == "train"


def test_training_dataset_report_includes_direction_baselines():
    from astro_abm.analysis.training_dataset import (
        compute_direction_baselines,
        format_training_dataset_report,
        summarize_training_dataset,
    )

    frame = pd.DataFrame(
        [
            {
                "ts": datetime(2024, 1, 1, 0, tzinfo=UTC),
                "symbol": "BTCUSDT",
                "regime_return_24h": 0.01,
                "future_return_24h": 0.02,
                "split": "train",
            },
            {
                "ts": datetime(2024, 1, 2, 0, tzinfo=UTC),
                "symbol": "BTCUSDT",
                "regime_return_24h": -0.01,
                "future_return_24h": -0.03,
                "split": "test",
            },
        ]
    )

    summary = summarize_training_dataset(frame)
    baselines = compute_direction_baselines(frame)
    report = format_training_dataset_report(summary, baselines)

    assert summary["rows"] == 2
    assert summary["feature_count"] == 1
    assert summary["label_count"] == 1
    assert any(row["rule"] == "momentum_24h" for row in baselines)
    assert "Direction Baselines" in report
    assert "test/momentum_24h" in report

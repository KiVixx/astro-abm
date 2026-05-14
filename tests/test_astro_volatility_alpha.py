from datetime import UTC, datetime, timedelta

import pandas as pd


def test_astro_volatility_alpha_scores_feature_tail_lift():
    from astro_abm.analysis.astro_volatility_alpha import build_astro_volatility_alpha_report

    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(240):
        phase = float(index % 100)
        rows.append(
            {
                "ts": start + timedelta(hours=index),
                "symbol": "BTCUSDT",
                "split": "train" if index < 160 else "test",
                "future_abs_return_24h": 0.10 if phase >= 90 else 0.01,
                "moon_phase_pct": phase,
            }
        )

    report = build_astro_volatility_alpha_report(
        pd.DataFrame(rows),
        target="future_abs_return_24h",
        event_mode="fixed_train_quantile",
        event_quantile=0.95,
        feature_quantile=0.9,
        min_observations=5,
    )

    high_signal = next(
        row
        for row in report.results
        if row["feature"] == "moon_phase_pct" and row["tail"] == "high" and row["split"] == "test"
    )
    assert high_signal["lift"] > 1.0
    assert high_signal["event_rate_signal"] > high_signal["event_rate_base"]


def test_astro_volatility_alpha_can_use_rolling_relative_volatility_events():
    from astro_abm.analysis.astro_volatility_alpha import build_astro_volatility_alpha_report

    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(180):
        phase = float(index % 10)
        high_local_vol = phase >= 9
        mature_market = index >= 90
        rows.append(
            {
                "ts": start + timedelta(hours=index),
                "symbol": "BTCUSDT",
                "split": "train" if index < 90 else "test",
                "future_abs_return_24h": 0.10 if high_local_vol and not mature_market else 0.03 if high_local_vol else 0.01,
                "moon_phase_pct": phase,
            }
        )

    report = build_astro_volatility_alpha_report(
        pd.DataFrame(rows),
        target="future_abs_return_24h",
        event_mode="rolling_quantile",
        event_quantile=0.9,
        event_window_hours=20,
        event_min_periods=10,
        feature_quantile=0.9,
        min_observations=2,
    )

    high_signal = next(
        row
        for row in report.results
        if row["feature"] == "moon_phase_pct" and row["tail"] == "high" and row["split"] == "test"
    )
    assert report.event_mode == "rolling_quantile"
    assert high_signal["lift"] > 1.0

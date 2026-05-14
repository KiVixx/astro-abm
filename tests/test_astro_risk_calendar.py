from datetime import UTC, datetime, timedelta

import pandas as pd


def test_build_astro_risk_calendar_scores_future_feature_rules():
    from astro_abm.analysis.astro_risk_calendar import build_astro_risk_calendar

    start = datetime(2026, 1, 1, tzinfo=UTC)
    ephemeris = pd.DataFrame(
        [
            {"ts": start + timedelta(hours=0), "venus_speed_abs": 0.5, "mercury_days_to_station_nearest": 8.0},
            {"ts": start + timedelta(hours=1), "venus_speed_abs": 0.1, "mercury_days_to_station_nearest": 2.0},
            {"ts": start + timedelta(hours=2), "venus_speed_abs": 0.2, "mercury_days_to_station_nearest": 9.0},
        ]
    )
    signals = pd.DataFrame(
        [
            {"feature": "venus_speed_abs", "tail": "low", "threshold": 0.2, "lift": 1.8, "observations_signal": 100},
            {
                "feature": "mercury_days_to_station_nearest",
                "tail": "low",
                "threshold": 3.0,
                "lift": 1.6,
                "observations_signal": 100,
            },
        ]
    )

    calendar = build_astro_risk_calendar(ephemeris, signals, frequency="hourly")

    assert list(calendar["active_signal_count"]) == [0, 2, 1]
    assert calendar.loc[1, "risk_score_0_100"] == 100.0
    assert "venus_speed_abs:low" in calendar.loc[1, "active_signals"]


def test_build_astro_risk_calendar_daily_keeps_highest_hour():
    from astro_abm.analysis.astro_risk_calendar import build_astro_risk_calendar

    start = datetime(2026, 1, 1, tzinfo=UTC)
    ephemeris = pd.DataFrame(
        [
            {"ts": start + timedelta(hours=0), "venus_speed_abs": 0.5},
            {"ts": start + timedelta(hours=12), "venus_speed_abs": 0.1},
            {"ts": start + timedelta(days=1), "venus_speed_abs": 0.1},
        ]
    )
    signals = pd.DataFrame(
        [{"feature": "venus_speed_abs", "tail": "low", "threshold": 0.2, "lift": 1.8, "observations_signal": 100}]
    )

    calendar = build_astro_risk_calendar(ephemeris, signals, frequency="daily")

    assert len(calendar) == 2
    assert calendar.loc[0, "risk_score_0_100"] == 100.0

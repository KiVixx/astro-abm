from __future__ import annotations

import math
from datetime import UTC, datetime

import pandas as pd
import pytest

from astro_daily.retrograde import STATION_OUT, StationEvent
from research.mercury_station_tsla import (
    WindowSpec,
    _select_window,
    _window_metrics,
    _deterministic_cap,
    bootstrap_difference_ci,
    build_market_panel,
    load_price_csv,
    price_data_quality,
    run_mercury_tsla_study,
)


def _price_frame(asset: str, start: str, periods: int, growth: float) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=periods, tz="UTC")
    return pd.DataFrame(
        {
            "ts": dates,
            "asset": asset,
            "price": [100 * ((1 + growth) ** index) for index in range(periods)],
        }
    )


def test_load_price_csv_rejects_duplicate_dates(tmp_path):
    path = tmp_path / "duplicate.csv"
    pd.DataFrame(
        {
            "date": ["2020-01-02", "2020-01-02"],
            "close": [10, 11],
        }
    ).to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate dates"):
        load_price_csv(path, asset="TSLA")


def test_market_panel_uses_prior_data_for_extreme_threshold():
    tsla = _price_frame("TSLA", "2020-01-01", 300, 0.001)
    spx = _price_frame("SPX", "2020-01-01", 300, 0.0005)
    panel = build_market_panel(tsla, spx)
    original = panel.loc[100, "is_extreme_move"]
    tsla.loc[250:, "price"] *= 10
    changed = build_market_panel(tsla, spx)
    assert changed.loc[100, "is_extreme_move"] == original


def test_calendar_and_trading_windows_are_directional():
    panel = build_market_panel(
        _price_frame("TSLA", "2020-01-01", 30, 0.01),
        _price_frame("SPX", "2020-01-01", 30, 0.001),
    )
    anchor = pd.Timestamp("2020-01-10", tz="UTC")
    calendar = _select_window(
        panel,
        anchor,
        WindowSpec("late", "calendar", 8, 14),
    )
    trading = _select_window(
        panel,
        anchor,
        WindowSpec("late_sessions", "trading", 6, 10),
    )
    assert calendar["ts"].min() >= anchor + pd.Timedelta(days=8)
    assert len(trading) == 5
    assert trading.iloc[0]["ts"] == panel[panel["ts"] > anchor].iloc[5]["ts"]


def test_window_metrics_include_spx_excess_and_clamped_frequency():
    panel = build_market_panel(
        _price_frame("TSLA", "2020-01-01", 100, 0.01),
        _price_frame("SPX", "2020-01-01", 100, 0.002),
    )
    metrics = _window_metrics(panel.iloc[70:80])
    assert metrics["cumulative_return"] > 0
    assert metrics["cumulative_excess_return_vs_spx"] > 0
    assert 0 <= metrics["positive_day_frequency"] <= 1
    assert metrics["max_drawdown"] <= 0


def test_bootstrap_difference_ci_is_deterministic():
    first = bootstrap_difference_ci([1, 2, 3], [0, 0, 1], samples=200, seed=7)
    second = bootstrap_difference_ci([1, 2, 3], [0, 0, 1], samples=200, seed=7)
    assert first == second
    assert first[0] < first[1]


def test_inference_baseline_cap_is_deterministic():
    values = list(range(100))
    first = _deterministic_cap(values, limit=10, seed=7)
    second = _deterministic_cap(values, limit=10, seed=7)
    assert first.tolist() == second.tolist()
    assert len(first) == 10


def test_price_quality_reports_clean_coverage():
    frame = _price_frame("TSLA", "2020-01-01", 5, 0.01)
    quality = price_data_quality(frame)
    assert quality["rows"] == 5
    assert quality["duplicate_dates"] == 0
    assert quality["nonpositive_prices"] == 0


def test_station_event_shape_is_utc_and_station_out():
    event = StationEvent(
        exact_ts=datetime(2020, 7, 12, 8, tzinfo=UTC),
        body="Mercury",
        station_type=STATION_OUT,
    )
    assert event.date.isoformat() == "2020-07-12"
    assert event.station_type == "retrograde_to_direct"


def test_study_runs_without_network_and_returns_directional_window():
    tsla = _price_frame("TSLA", "2020-01-01", 320, 0.001)
    spx = _price_frame("SPX", "2020-01-01", 320, 0.0005)
    events = [
        StationEvent(
            exact_ts=tsla.iloc[index]["ts"].to_pydatetime(),
            body="Mercury",
            station_type=STATION_OUT,
        )
        for index in (100, 200)
    ]
    config = {
        "study": {"study_id": "test"},
        "windows": {
            "post_late_calendar_8_14": {
                "mode": "calendar",
                "start": 8,
                "end": 14,
            }
        },
        "baselines": "non_event",
        "metrics": "cumulative_return",
        "statistics": {
            "random_seed": 7,
            "bootstrap_samples": 20,
            "permutation_samples": 20,
            "baseline_samples_per_event": 5,
            "inference_baseline_cap": 10,
            "event_exclusion_days": 14,
        },
    }
    result = run_mercury_tsla_study(
        config=config,
        config_text="study: test\n",
        tsla=tsla,
        spx=spx,
        station_events=events,
    )
    assert len(result.results) == 1
    assert result.results.iloc[0]["window_name"] == "post_late_calendar_8_14"
    assert result.results.iloc[0]["n_events"] == 2
    assert result.event_metrics["era"].notna().all()

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from astro_daily.retrograde import STATION_OUT, StationEvent
from research.mercury_station_tsla import WindowSpec, build_market_panel
from research.mercury_station_tsla_reversal import (
    _first_full_tsla_session_after,
    reversal_record,
    run_mercury_tsla_reversal_study,
)


def _panel_from_returns(tsla_returns: list[float], spx_return: float = 0.0) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(tsla_returns) + 1, tz="UTC")
    tsla_prices = [100.0]
    spx_prices = [100.0]
    for value in tsla_returns:
        tsla_prices.append(tsla_prices[-1] * (1 + value))
        spx_prices.append(spx_prices[-1] * (1 + spx_return))
    tsla = pd.DataFrame({"ts": dates, "asset": "TSLA", "price": tsla_prices})
    spx = pd.DataFrame({"ts": dates, "asset": "SPX", "price": spx_prices})
    return build_market_panel(tsla, spx)


def test_downtrend_then_rebound_is_reversal():
    panel = _panel_from_returns([-0.02] * 20 + [0.03] * 10)
    anchor = panel.iloc[20]["ts"]
    record = reversal_record(
        panel=panel,
        anchor=anchor,
        window=WindowSpec("post", "trading", 1, 5),
        trend_horizon=10,
        strong_trend_threshold=0.5,
    )
    assert record is not None
    assert record["pre_trend_direction"] == -1
    assert record["post_excess_return"] > 0
    assert record["reversal_frequency"] == 1
    assert record["normalized_reversal_strength"] > 0


def test_same_direction_move_is_not_reversal():
    panel = _panel_from_returns([0.01] * 30)
    anchor = panel.iloc[20]["ts"]
    record = reversal_record(
        panel=panel,
        anchor=anchor,
        window=WindowSpec("post", "trading", 1, 5),
        trend_horizon=10,
        strong_trend_threshold=0.5,
    )
    assert record is not None
    assert record["pre_trend_direction"] == 1
    assert record["post_excess_return"] > 0
    assert record["reversal_frequency"] == 0
    assert record["normalized_reversal_strength"] < 0


def test_anchor_day_price_is_not_used_in_prior_trend():
    returns = [-0.01] * 20 + [0.01] * 10
    original = _panel_from_returns(returns)
    anchor = original.iloc[20]["ts"]
    changed = original.copy()
    changed.loc[changed["ts"] == anchor, "excess_log_ret"] = 10.0
    first = reversal_record(
        panel=original,
        anchor=anchor,
        window=WindowSpec("post", "trading", 1, 5),
        trend_horizon=10,
        strong_trend_threshold=0.5,
    )
    second = reversal_record(
        panel=changed,
        anchor=anchor,
        window=WindowSpec("post", "trading", 1, 5),
        trend_horizon=10,
        strong_trend_threshold=0.5,
    )
    assert first is not None and second is not None
    assert first["pre_excess_return"] == second["pre_excess_return"]


def test_first_full_session_after_station_respects_market_open():
    panel = _panel_from_returns([0.001] * 10)
    before_open = pd.Timestamp("2020-01-06T13:00:00Z")
    during_session = pd.Timestamp("2020-01-06T16:00:00Z")
    assert _first_full_tsla_session_after(panel, before_open) == pd.Timestamp(
        "2020-01-06T00:00:00Z"
    )
    assert _first_full_tsla_session_after(panel, during_session) == pd.Timestamp(
        "2020-01-07T00:00:00Z"
    )


def test_reversal_study_runs_without_network():
    returns = [0.001, -0.002, 0.003, -0.001] * 100
    panel = _panel_from_returns(returns, spx_return=0.0002)
    tsla = panel[["ts", "tsla_price"]].rename(columns={"tsla_price": "price"})
    tsla["asset"] = "TSLA"
    spx = panel[["ts", "spx_price"]].rename(columns={"spx_price": "price"})
    spx["asset"] = "SPX"
    events = [
        StationEvent(
            exact_ts=panel.iloc[index]["ts"].to_pydatetime(),
            body="Mercury",
            station_type=STATION_OUT,
        )
        for index in (100, 200, 300)
    ]
    config = {
        "study": {"study_id": "reversal_test"},
        "trend_horizons": "20",
        "windows": {
            "station_to_day8_calendar_0_8": {
                "mode": "anchored_calendar",
                "start": 0,
                "end": 8,
            }
        },
        "baselines": "volatility_regime_matched",
        "metrics": "reversal_frequency,normalized_reversal_strength",
        "primary_hypothesis": {
            "trend_horizon_sessions": 20,
            "window_name": "station_to_day8_calendar_0_8",
            "baseline_method": "volatility_regime_matched",
            "metrics": "reversal_frequency,normalized_reversal_strength",
        },
        "statistics": {
            "random_seed": 7,
            "bootstrap_samples": 20,
            "permutation_samples": 20,
            "baseline_samples_per_event": 5,
            "inference_baseline_cap": 10,
            "event_exclusion_days": 14,
            "strong_trend_z_threshold": 0.5,
        },
    }
    result = run_mercury_tsla_reversal_study(
        config=config,
        config_text="study: reversal_test\n",
        tsla=tsla[["ts", "asset", "price"]],
        spx=spx[["ts", "asset", "price"]],
        station_events=events,
    )
    assert len(result.results) == 2
    assert set(result.results["test_family"]) == {"primary_reversal"}
    assert result.results["q_value_fdr"].notna().all()

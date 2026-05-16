from __future__ import annotations

import math

import pandas as pd

from research.bootstrap import bootstrap_ci
from research.config import EventStudyConfig
from research.event_study import run_event_study
from research.event_windows import select_event_windows
from research.multiple_testing import benjamini_hochberg


def test_event_window_join_and_baseline_exclusion(tmp_path):
    market = pd.DataFrame(
        {
            "ts": pd.date_range("2020-01-01", periods=10, freq="D", tz="UTC"),
            "asset": "BTC",
            "source": "synthetic",
            "log_ret_1d": [0.0, 0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.01, 0.04, -0.02],
            "is_extreme_absret_95": [False, False, True, False, False, False, False, False, True, False],
        }
    )
    market["ret_1d"] = market["log_ret_1d"]
    event_windows = pd.DataFrame(
        {
            "ts": pd.date_range("2020-01-02", periods=3, freq="D", tz="UTC"),
            "event_id": "Mercury_direct_to_retrograde_202001030000_pm1d",
            "event_type": "mercury_direct_to_retrograde",
            "exact_date_ts": pd.Timestamp("2020-01-03", tz="UTC"),
            "rel_day": [-1, 0, 1],
            "window_name": "station_pm_1d",
        }
    )
    market_path = tmp_path / "market.parquet"
    events_path = tmp_path / "events.parquet"
    features_path = tmp_path / "features.parquet"
    market.to_parquet(market_path)
    event_windows.to_parquet(events_path)
    pd.DataFrame({"ts": market["ts"]}).to_parquet(features_path)

    config = EventStudyConfig(
        run_id="test",
        data_version="v1",
        calc_version="v1",
        random_seed=7,
        bootstrap_samples=25,
        placebo_samples=20,
        market_features_path=str(market_path),
        astro_event_windows_path=str(events_path),
        astro_daily_features_path=str(features_path),
        aspect_chunks_dir="",
        event_groups={"mercury_station": {"kind": "station", "body": "Mercury"}},
        windows=("-1,1",),
        baseline_types=("all_non_event",),
        exclude_event_windows=True,
    )

    result = run_event_study(config).results

    mean_row = result[result["metric"] == "mean_return"].iloc[0]
    assert mean_row["n_events"] == 1
    assert mean_row["n_observations"] == 3
    assert math.isclose(mean_row["effect_value"], (0.01 - 0.02 + 0.03) / 3)
    assert mean_row["baseline_value"] != mean_row["effect_value"]


def test_select_daily_feature_threshold_events():
    features = pd.DataFrame(
        {
            "ts": pd.date_range("2020-01-01", periods=4, freq="D", tz="UTC"),
            "station_cluster_count_7d": [1, 2, 0, 3],
        }
    )

    selection = select_event_windows(
        event_type="station_cluster_7d",
        group={"kind": "daily_feature_threshold", "feature": "station_cluster_count_7d", "min_value": 2},
        window_name="-1,1",
        astro_event_windows=pd.DataFrame(),
        astro_daily_features=features,
    )

    assert selection.events["event_id"].nunique() == 2
    assert len(selection.events) == 6


def test_bootstrap_seed_is_deterministic():
    first = bootstrap_ci([1, 2, 3, 4], samples=100, seed=123)
    second = bootstrap_ci([1, 2, 3, 4], samples=100, seed=123)

    assert first == second


def test_fdr_correction_monotonic():
    q_values = benjamini_hochberg([0.01, 0.04, 0.03, 0.2])

    assert q_values[0] <= q_values[2] <= q_values[3]

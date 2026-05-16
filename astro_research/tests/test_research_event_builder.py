from __future__ import annotations

import pandas as pd

from research.research_events import build_research_events


def test_research_event_ids_are_deterministic(tmp_path):
    windows = pd.DataFrame(
        {
            "ts": [pd.Timestamp("2020-01-01", tz="UTC")],
            "event_id": ["Mercury_direct_to_retrograde_202001010000_pm7d"],
            "event_type": ["mercury_direct_to_retrograde"],
            "body": ["Mercury"],
            "body_a": [None],
            "body_b": [None],
            "aspect_name": [None],
            "phase_name": [None],
            "exact_ts": [pd.Timestamp("2020-01-01", tz="UTC")],
            "exact_date_ts": [pd.Timestamp("2020-01-01", tz="UTC")],
            "rel_day": [0],
            "window_name": ["station_pm_7d"],
        }
    )
    windows_path = tmp_path / "windows.parquet"
    windows.to_parquet(windows_path)
    daily_path = tmp_path / "daily.parquet"
    pd.DataFrame({"ts": [pd.Timestamp("2020-01-01", tz="UTC")], "station_cluster_count_7d": [0]}).to_parquet(daily_path)
    config = tmp_path / "events.yaml"
    config.write_text(
        f'''dataset:
  data_version: "test"
  dataset_id: "test"
  calc_version: "test"
inputs:
  astro_event_windows_path: "{windows_path}"
  astro_daily_features_path: "{daily_path}"
  aspect_chunks_dir: ""
  moon_phase_events_path: ""
event_families:
  station_bodies: "Mercury"
  station_cluster_count_7d_gte: 2
  active_retrograde_count_gte: 3
  moon_phases: "NewMoon,FullMoon"
overlap:
  policy: "allow_overlap"
  window_days: 7
'''
    )

    first = build_research_events(config).events
    second = build_research_events(config).events

    assert first.loc[0, "event_id"] == second.loc[0, "event_id"]
    assert first.loc[0, "event_family"] == "mercury_station"

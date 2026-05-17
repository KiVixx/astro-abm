from __future__ import annotations

import pandas as pd

from research.io import discover_aspect_chunk_files
from research.research_events import build_research_events
from research.research_events import _merge_cluster_days


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


def test_aspect_chunk_discovery_prefers_parquet(tmp_path):
    chunk = tmp_path / "aspects" / "year=2020" / "body_pair=Mars_Saturn"
    chunk.mkdir(parents=True)
    (chunk / "astro_aspect_events.csv").write_text("event_id\ncsv\n")
    pd.DataFrame({"event_id": ["parquet"]}).to_parquet(chunk / "astro_aspect_events.parquet")

    files = discover_aspect_chunk_files(tmp_path / "aspects", table_name="astro_aspect_events")

    assert files == [chunk / "astro_aspect_events.parquet"]


def test_aspect_event_normalization_and_mars_saturn_filter(tmp_path):
    chunk = tmp_path / "aspects" / "year=2020" / "body_pair=Mars_Saturn"
    chunk.mkdir(parents=True)
    pd.DataFrame(
        {
            "exact_ts": pd.to_datetime(["2020-01-01", "2020-03-01", "2020-05-01"], utc=True),
            "dataset_id": ["test"] * 3,
            "event_id": ["ms_conj", "ms_square", "ms_trine"],
            "body_a": ["Mars", "Mars", "Mars"],
            "body_b": ["Saturn", "Saturn", "Saturn"],
            "aspect_name": ["conjunction", "square", "trine"],
            "aspect_deg": [0, 90, 120],
            "exact_delta_deg": [0.0, 0.0, 0.0],
            "relative_speed_deg_day": [1.0, 1.0, 1.0],
            "applying_before": [True, True, True],
            "calc_version": ["test"] * 3,
            "source_note": ["test"] * 3,
        }
    ).to_parquet(chunk / "astro_aspect_events.parquet")
    config = tmp_path / "events.yaml"
    config.write_text(
        f'''dataset:
  data_version: "test"
  dataset_id: "test"
  calc_version: "test"
inputs:
  astro_event_windows_path: ""
  astro_daily_features_path: ""
  moon_phase_events_path: ""
aspect_inputs:
  macro_core:
    aspect_chunks_dir: "{tmp_path / 'aspects'}"
    aspect_profile: "macro_core"
    body_pairs: "Mars_Saturn"
    aspect_names: "conjunction,square,trine"
    hard_aspects: "conjunction,square,opposition"
    cluster_window_days: "14"
    cluster_percentile: 0.90
    cluster_merge_days: 7
event_families:
  station_bodies: ""
  station_cluster_count_7d_gte: 2
  active_retrograde_count_gte: 3
  moon_phases: ""
overlap:
  policy: "allow_overlap"
  window_days: 7
'''
    )

    events = build_research_events(config).events
    hard = events[events["event_family"] == "mars_saturn_hard_aspect"]

    assert set(hard["aspect_name"]) == {"conjunction", "square"}
    assert set(hard["event_type"]) == {"mars_saturn_conjunction", "mars_saturn_square"}
    assert hard["eligible_for_event_study"].all()


def test_macro_core_cluster_generation_and_overlap_merge(tmp_path):
    chunk = tmp_path / "aspects" / "year=2020" / "body_pair=Jupiter_Saturn"
    chunk.mkdir(parents=True)
    pd.DataFrame(
        {
            "exact_ts": pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-05", "2020-06-01"], utc=True),
            "dataset_id": ["test"] * 4,
            "event_id": ["a", "b", "c", "d"],
            "body_a": ["Jupiter"] * 4,
            "body_b": ["Saturn"] * 4,
            "aspect_name": ["conjunction", "square", "opposition", "trine"],
            "aspect_deg": [0, 90, 180, 120],
            "exact_delta_deg": [0.0] * 4,
            "relative_speed_deg_day": [1.0] * 4,
            "applying_before": [True] * 4,
            "calc_version": ["test"] * 4,
            "source_note": ["test"] * 4,
        }
    ).to_parquet(chunk / "astro_aspect_events.parquet")
    config = tmp_path / "events.yaml"
    config.write_text(
        f'''dataset:
  data_version: "test"
  dataset_id: "test"
  calc_version: "test"
inputs:
  astro_event_windows_path: ""
  astro_daily_features_path: ""
  moon_phase_events_path: ""
aspect_inputs:
  macro_core:
    aspect_chunks_dir: "{tmp_path / 'aspects'}"
    aspect_profile: "macro_core"
    body_pairs: "Jupiter_Saturn"
    aspect_names: "conjunction,square,trine,opposition"
    cluster_window_days: "14"
    cluster_percentile: 0.90
    cluster_merge_days: 7
event_families:
  station_bodies: ""
  station_cluster_count_7d_gte: 2
  active_retrograde_count_gte: 3
  moon_phases: ""
overlap:
  policy: "cluster_overlapping_events"
  window_days: 7
'''
    )

    events = build_research_events(config).events
    clusters = events[events["event_family"] == "macro_core_aspect_cluster"]

    assert not clusters.empty
    assert clusters["eligible_for_event_study"].any()
    assert clusters["event_type"].str.contains("macro_core_cluster_p90_14d").any()


def test_cluster_overlapping_events_merge_peak():
    selected = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-11"], utc=True),
            "count": [2, 5, 3],
        }
    )

    merged = _merge_cluster_days(selected, merge_days=7)

    assert len(merged) == 2
    assert merged.iloc[0]["ts"] == pd.Timestamp("2020-01-03", tz="UTC")


def test_h003_h004_not_no_eligible_rows_when_aspect_input_exists(tmp_path):
    chunk = tmp_path / "aspects" / "year=2020" / "body_pair=Mars_Saturn"
    chunk.mkdir(parents=True)
    pd.DataFrame(
        {
            "exact_ts": pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-05"], utc=True),
            "dataset_id": ["test"] * 3,
            "event_id": ["a", "b", "c"],
            "body_a": ["Mars"] * 3,
            "body_b": ["Saturn"] * 3,
            "aspect_name": ["conjunction", "square", "opposition"],
            "aspect_deg": [0, 90, 180],
            "exact_delta_deg": [0.0] * 3,
            "relative_speed_deg_day": [1.0] * 3,
            "applying_before": [True] * 3,
            "calc_version": ["test"] * 3,
            "source_note": ["test"] * 3,
        }
    ).to_parquet(chunk / "astro_aspect_events.parquet")
    config = tmp_path / "events.yaml"
    config.write_text(
        f'''dataset:
  data_version: "test"
  dataset_id: "test"
  calc_version: "test"
inputs:
  astro_event_windows_path: ""
  astro_daily_features_path: ""
  moon_phase_events_path: ""
aspect_inputs:
  macro_core:
    aspect_chunks_dir: "{tmp_path / 'aspects'}"
    aspect_profile: "macro_core"
    body_pairs: "Mars_Saturn"
    aspect_names: "conjunction,square,opposition"
    cluster_window_days: "14"
    cluster_percentile: 0.90
    cluster_merge_days: 7
event_families:
  station_bodies: ""
  station_cluster_count_7d_gte: 2
  active_retrograde_count_gte: 3
  moon_phases: ""
overlap:
  policy: "allow_overlap"
  window_days: 7
'''
    )

    events = build_research_events(config).events

    assert (events["event_family"] == "mars_saturn_hard_aspect").any()
    assert (events["event_family"] == "macro_core_aspect_cluster").any()

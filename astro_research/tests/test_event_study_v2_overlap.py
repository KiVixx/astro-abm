from __future__ import annotations

import pandas as pd

from research.research_events import _apply_overlap_policy


def test_overlap_policy_clusters_nearby_events():
    events = pd.DataFrame(
        {
            "event_family": ["station_cluster", "station_cluster"],
            "event_ts": pd.to_datetime(["2020-01-01", "2020-01-05"], utc=True),
            "event_id": ["a", "b"],
            "eligible_for_event_study": [True, True],
            "is_overlapping": [False, False],
            "is_primary": [True, True],
            "exclusion_reason": ["", ""],
        }
    )

    clustered = _apply_overlap_policy(events, policy="cluster_overlapping_events", window_days=7)

    assert clustered.loc[1, "is_overlapping"] is True or bool(clustered.loc[1, "is_overlapping"])
    assert clustered.loc[1, "eligible_for_event_study"] is False or not bool(clustered.loc[1, "eligible_for_event_study"])

from __future__ import annotations

from research.multiple_testing import benjamini_hochberg
import pandas as pd

from research.event_study_v2 import _event_coverage


def test_fdr_group_input_is_order_preserving():
    q_values = benjamini_hochberg([0.01, 0.20, 0.03])

    assert q_values[0] <= q_values[1]
    assert len(q_values) == 3


def test_coverage_aware_event_counts():
    event_window = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-02-01"], utc=True),
            "event_id": ["a", "a", "b"],
        }
    )
    panel = pd.DataFrame({"ts": pd.to_datetime(["2020-01-02"], utc=True)})

    coverage = _event_coverage(event_window, panel, total_events=2)

    assert coverage["n_events_with_asset_coverage"] == 1
    assert coverage["n_events_total"] == 2
    assert coverage["coverage_pct"] == 0.5

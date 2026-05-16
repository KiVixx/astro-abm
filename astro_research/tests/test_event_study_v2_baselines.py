from __future__ import annotations

import pandas as pd

from research.event_study_v2 import _baseline_panel


def test_event_study_v2_baseline_excludes_event_windows():
    panel = pd.DataFrame({"ts": pd.date_range("2020-01-01", periods=5, freq="D", tz="UTC"), "realized_vol_20d": [1, 1, 2, 2, 3]})
    events = pd.DataFrame({"ts": pd.to_datetime(["2020-01-02", "2020-01-03"], utc=True)})

    baseline = _baseline_panel(panel, events, "non_event")

    assert not set(events["ts"]).intersection(set(baseline["ts"]))

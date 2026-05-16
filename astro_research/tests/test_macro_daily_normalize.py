from __future__ import annotations

import pandas as pd

from research.coverage import build_asset_coverage
from research.coverage import build_series_coverage


def test_coverage_start_end_calculation():
    frame = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01", "2020-01-03"], utc=True),
            "asset": ["SPX", "SPX"],
            "source": ["local_csv", "local_csv"],
        }
    )

    coverage = build_asset_coverage(frame, data_version="test")

    assert coverage.loc[0, "observation_count"] == 2
    assert coverage.loc[0, "missing_count"] == 1
    assert coverage.loc[0, "coverage_start_ts"] == pd.Timestamp("2020-01-01", tz="UTC")


def test_weekly_monthly_frequency_adjusted_missing_count():
    frame = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-03", "2020-01-10", "2020-01-01", "2020-02-01"], utc=True),
            "series_id": ["NFCI", "NFCI", "USREC", "USREC"],
            "source": ["fred", "fred", "fred", "fred"],
            "value": [0.1, 0.2, 0, 1],
            "original_frequency": ["weekly", "weekly", "monthly", "monthly"],
        }
    )

    coverage = build_series_coverage(frame, data_version="test")
    nfci = coverage[coverage["asset"] == "NFCI"].iloc[0]
    usrec = coverage[coverage["asset"] == "USREC"].iloc[0]

    assert nfci["calendar_missing_count"] > nfci["frequency_adjusted_missing_count"]
    assert nfci["frequency_adjusted_missing_count"] == 0
    assert usrec["frequency_adjusted_missing_count"] == 0

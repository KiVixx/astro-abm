from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from research.local_data_fetch import (
    credit_proxy_from_observations,
    lbma_gold_to_price_frame,
    update_local_data_provenance,
    yahoo_chart_to_price_frame,
    LocalDataFetchResult,
)


def test_yahoo_chart_to_price_frame_normalizes_ohlcv():
    payload = {
        "timestamp": [1577923200, 1578009600],
        "indicators": {
            "quote": [
                {
                    "open": [100.0, 101.0],
                    "high": [102.0, 103.0],
                    "low": [99.0, 100.0],
                    "close": [101.0, 102.0],
                    "volume": [10, 11],
                }
            ],
            "adjclose": [{"adjclose": [101.0, 102.0]}],
        },
    }

    frame = yahoo_chart_to_price_frame(payload, start=date(2020, 1, 1), end=date(2020, 1, 3))

    assert list(frame.columns) == ["date", "open", "high", "low", "close", "adj_close", "volume"]
    assert frame.iloc[0].to_dict() == {
        "date": "2020-01-02",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "adj_close": 101.0,
        "volume": 10,
    }


def test_lbma_gold_uses_pm_with_am_fallback():
    pm = [
        {"d": "2020-01-02", "v": [1520.0, 0, 0]},
        {"d": "2020-01-03", "v": [None, 0, 0]},
    ]
    am = [
        {"d": "2020-01-02", "v": [1510.0, 0, 0]},
        {"d": "2020-01-03", "v": [1530.0, 0, 0]},
    ]

    frame = lbma_gold_to_price_frame(pm, am, start=date(2020, 1, 1), end=date(2020, 1, 5))

    assert list(frame["date"]) == ["2020-01-02", "2020-01-03"]
    assert list(frame["close"]) == [1520.0, 1530.0]


def test_credit_proxy_from_observations_forward_fills_business_days():
    aaa = pd.DataFrame({"ts": ["2020-01-01", "2020-02-01"], "value": [3.0, 3.5]})
    baa = pd.DataFrame({"ts": ["2020-01-01", "2020-02-01"], "value": [5.0, 5.2]})

    frame = credit_proxy_from_observations(aaa=aaa, baa=baa, start=date(2020, 1, 1), end=date(2020, 1, 7))

    assert list(frame["date"]) == ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    assert set(frame["value"]) == {2.0}


def test_update_local_data_provenance_records_generated_outputs(tmp_path: Path):
    provenance = tmp_path / "astro_research/data/local/LOCAL_DATA_PROVENANCE.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text(json.dumps({"schema_version": "local_data_provenance_v1", "series": []}))

    update_local_data_provenance(
        tmp_path,
        (
            LocalDataFetchResult(
                asset="CreditProxy",
                output_path=tmp_path / "astro_research/data/local/credit/hy_oas_daily.csv",
                rows=2,
                coverage_start="2020-01-01",
                coverage_end="2020-01-02",
                source="FRED BAA minus AAA",
            ),
        ),
    )

    payload = json.loads(provenance.read_text())
    credit = payload["series"][0]
    assert credit["asset"] == "HY_OAS_PROXY"
    assert credit["proxy_type"] == "BAA_MINUS_AAA"
    assert credit["not_equivalent_to"] == "ICE_BofA_HY_OAS"
    assert credit["rows"] == 2

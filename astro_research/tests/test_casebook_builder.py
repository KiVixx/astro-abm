from __future__ import annotations

import pandas as pd

from research.casebook import build_casebook


def test_casebook_handles_missing_market_coverage(tmp_path):
    catalog = tmp_path / "catalog.csv"
    catalog.write_text(
        "event_id,event_name,start_date,end_date,category,region,country,severity_score,source,source_url,date_confidence,notes\n"
        "case,Case,2020-01-01,2020-01-02,test,global,,1,manual,,high,test\n"
    )
    events = tmp_path / "events.parquet"
    pd.DataFrame({"event_ts": [pd.Timestamp("2020-01-01", tz="UTC")], "event_family": ["moon_phase"]}).to_parquet(events)
    config = tmp_path / "casebook.yaml"
    config.write_text(
        f'''dataset:
  data_version: "test"
inputs:
  crisis_catalog_path: "{catalog}"
  research_events_path: "{events}"
  market_features_path: ""
  financial_stress_path: ""
window_days: 90
'''
    )

    paths = build_casebook(config, output_dir=tmp_path / "out")

    assert len(paths) == 1
    assert "no causal claim" in paths[0].read_text()
    assert "missing_component: `market_features`" in paths[0].read_text()


def test_casebook_reports_descriptive_market_stress_and_event_context(tmp_path):
    catalog = tmp_path / "catalog.csv"
    catalog.write_text(
        "event_id,event_name,start_date,end_date,category,region,country,severity_score,source,source_url,date_confidence,notes\n"
        "case,Case,2020-03-16,2020-03-16,market_crash,global,US,1,manual,,high,anchor\n"
    )
    events = tmp_path / "events.parquet"
    pd.DataFrame(
        {
            "event_ts": pd.to_datetime(["2020-03-15", "2020-03-17"], utc=True),
            "event_family": ["mars_saturn_hard_aspect", "macro_core_aspect_cluster"],
            "source_table": ["astro_aspect_events", "astro_aspect_events"],
            "is_primary": [True, False],
        }
    ).to_parquet(events)
    market = tmp_path / "market.parquet"
    pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-03-15", "2020-03-16", "2020-03-16"], utc=True),
            "asset": ["SPX", "SPX", "Gold"],
            "drawdown_60d": [-0.2, -0.3, -0.1],
            "realized_vol_20d": [0.4, 0.5, 0.2],
            "abs_ret_rank_252d": [0.9, 0.99, 0.8],
        }
    ).to_parquet(market)
    stress = tmp_path / "stress.parquet"
    pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-03-15", "2020-03-16"], utc=True),
            "cross_asset_stress_score": [0.7, 0.9],
            "component_count": [4, 5],
            "stress_regime": ["stress", "stress"],
        }
    ).to_parquet(stress)
    config = tmp_path / "casebook.yaml"
    config.write_text(
        f'''dataset:
  data_version: "test_casebook"
inputs:
  crisis_catalog_path: "{catalog}"
  research_events_path: "{events}"
  market_features_path: "{market}"
  financial_stress_path: "{stress}"
window_days: 90
'''
    )

    paths = build_casebook(config, output_dir=tmp_path / "out")
    text = paths[0].read_text()

    assert "data_version: `test_casebook`" in text
    assert "| SPX | 2 | 2020-03-15 | 2020-03-16 | -0.3000 | 0.5000 | 0.9900 |" in text
    assert "| mean_cross_asset_stress_score | 0.8000 |" in text
    assert "| mars_saturn_hard_aspect | astro_aspect_events | 1 | 1 |" in text
    assert "does not assert causality, prediction, investment advice, or a trading signal" in text

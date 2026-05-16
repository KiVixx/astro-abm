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

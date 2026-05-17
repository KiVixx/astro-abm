from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.event_study_v2 import (
    BatchStudyResult,
    top_findings_markdown,
    validate_exploratory_batch_outputs,
    write_batch_report,
)


def test_exploratory_batch_config_metadata():
    raw = _parse_simple_yaml(Path("astro_research/configs/research_batch_exploratory_v1.yaml").read_text())

    assert raw["run"]["run_type"] == "exploratory_formal_batch"
    assert raw["run"]["not_publication_grade"] is True
    assert raw["run"]["association_only"] is True
    assert raw["run"]["credit_proxy_used"] == "BAA_MINUS_AAA"
    assert "H001_station_cluster_stress" in raw["studies"]
    assert "H004_macro_core_aspect_cluster" in raw["studies"]


def test_top_findings_threshold_filter():
    results = pd.DataFrame(
        {
            "hypothesis_id": ["H1", "H2", "H3"],
            "asset": ["SPX", "SPX", "SPX"],
            "window_name": ["pm7", "pm7", "pm7"],
            "baseline_method": ["non_event", "non_event", "non_event"],
            "metric": ["realized_vol", "realized_vol", "realized_vol"],
            "q_value_fdr": [0.05, 0.20, 0.01],
            "effect_minus_baseline": [0.1, 0.2, 0.3],
            "sample_warning": ["", "", "insufficient_events"],
            "n_events_with_asset_coverage": [20, 20, 20],
        }
    )

    text = top_findings_markdown(results)

    assert "H1" in text
    assert "H2" not in text
    assert "H3" not in text
    assert "not causal" in text
    assert "trading signal" not in text.lower()


def test_top_findings_no_robust_findings_message():
    results = pd.DataFrame(
        {
            "hypothesis_id": ["H1"],
            "asset": ["SPX"],
            "window_name": ["pm7"],
            "baseline_method": ["non_event"],
            "metric": ["realized_vol"],
            "q_value_fdr": [0.5],
            "effect_minus_baseline": [0.1],
            "sample_warning": [""],
            "n_events_with_asset_coverage": [20],
        }
    )

    assert "No robust findings under current thresholds" in top_findings_markdown(results)


def test_validate_exploratory_batch_outputs_guardrails(tmp_path):
    results = pd.DataFrame(
        {
            "run_id": ["run"],
            "hypothesis_id": ["H1"],
            "event_family": ["station_cluster"],
            "asset": ["SPX"],
            "window_name": ["pm7"],
            "baseline_method": ["non_event"],
            "metric": ["realized_vol"],
        }
    )
    runs = pd.DataFrame({"run_type": ["exploratory_formal_batch"]})
    results.to_parquet(tmp_path / "results.parquet")
    runs.to_csv(tmp_path / "event_study_runs.csv", index=False)
    (tmp_path / "summary.md").write_text("Association only, not causal.")
    (tmp_path / "top_findings.md").write_text("No robust findings under current thresholds.")
    (tmp_path / "warnings.json").write_text(json.dumps({"warnings": [{"category": "licensing", "message": "review"}, {"category": "credit_proxy", "message": "BAA_MINUS_AAA"}]}))

    assert validate_exploratory_batch_outputs(tmp_path) == []


def test_warnings_include_licensing_and_proxy_caveats(tmp_path):
    batch = BatchStudyResult(
        results=pd.DataFrame(),
        runs=pd.DataFrame({"run_type": ["exploratory_formal_batch"], "hypothesis_id": ["H1"]}),
        warnings=[
            "licensing: Yahoo local data is local research only.",
            "credit_proxy: BAA_MINUS_AAA is not equivalent to ICE/BofA HY OAS.",
        ],
        run_id="test",
    )
    paths = write_batch_report(batch, tmp_path, config_text="run:\n", hypothesis_snapshot=pd.DataFrame({"hypothesis_id": ["H1"]}))
    payload = json.loads(paths["warnings.json"].read_text())
    text = json.dumps(payload)

    assert "licensing" in text
    assert "credit_proxy" in text

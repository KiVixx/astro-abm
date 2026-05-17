from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.event_study_v2 import (
    BatchStudyResult,
    RUN_MANIFEST_VERSION,
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
    _write_minimal_run_manifest(tmp_path)

    assert validate_exploratory_batch_outputs(tmp_path) == []


def test_validate_exploratory_batch_requires_aspect_traceability(tmp_path):
    results = pd.DataFrame(
        {
            "run_id": ["run"],
            "hypothesis_id": ["H003_mars_saturn_hard_aspects"],
            "event_family": ["mars_saturn_hard_aspect"],
            "asset": ["SPX"],
            "window_name": ["pm7"],
            "baseline_method": ["non_event"],
            "metric": ["realized_vol"],
        }
    )
    runs = pd.DataFrame({"run_type": ["exploratory_formal_batch"], "hypothesis_id": ["H003_mars_saturn_hard_aspects"]})
    traceability = pd.DataFrame(
        {
            "hypothesis_id": ["H003_mars_saturn_hard_aspects"],
            "event_family": ["mars_saturn_hard_aspect"],
            "source_table": ["astro_aspect_events"],
            "source_event_count": [2],
            "eligible_event_count": [2],
            "primary_event_count": [2],
            "source_event_id_examples": ["a,b"],
            "source_note": ["test"],
        }
    )
    results.to_parquet(tmp_path / "results.parquet")
    runs.to_csv(tmp_path / "event_study_runs.csv", index=False)
    traceability.to_csv(tmp_path / "event_traceability.csv", index=False)
    (tmp_path / "summary.md").write_text("Association only, not causal.")
    (tmp_path / "top_findings.md").write_text("No robust findings under current thresholds.")
    (tmp_path / "warnings.json").write_text(json.dumps({"warnings": [{"category": "licensing", "message": "review"}, {"category": "credit_proxy", "message": "BAA_MINUS_AAA"}]}))
    _write_minimal_run_manifest(tmp_path)

    assert validate_exploratory_batch_outputs(tmp_path) == []

    traceability.assign(source_table="astro_daily_features").to_csv(tmp_path / "event_traceability.csv", index=False)

    warnings = validate_exploratory_batch_outputs(tmp_path)

    assert any("must trace to astro_aspect_events" in warning for warning in warnings)


def test_warnings_include_licensing_and_proxy_caveats(tmp_path):
    batch = BatchStudyResult(
        results=pd.DataFrame(
            {
                "hypothesis_id": ["H1"],
                "asset": ["SPX"],
                "asset_start": [pd.Timestamp("2020-01-01", tz="UTC")],
                "asset_end": [pd.Timestamp("2020-01-02", tz="UTC")],
                "n_events_with_asset_coverage": [1],
                "n_events_total": [1],
                "coverage_pct": [1.0],
                "missing_components": [""],
                "coverage_warning": [""],
                "metric": ["realized_vol"],
                "q_value_fdr": [0.5],
                "sample_warning": [""],
                "window_name": ["pm7"],
                "baseline_method": ["non_event"],
                "effect_minus_baseline": [0.1],
            }
        ),
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
    assert paths["event_traceability.csv"].exists()
    assert paths["run_manifest.json"].exists()


def test_run_manifest_ties_batch_to_config_git_inputs_and_outputs(tmp_path):
    batch = BatchStudyResult(
        results=pd.DataFrame(
            {
                "hypothesis_id": ["H1"],
                "asset": ["SPX"],
                "asset_start": [pd.Timestamp("2020-01-01", tz="UTC")],
                "asset_end": [pd.Timestamp("2020-01-02", tz="UTC")],
                "n_events_with_asset_coverage": [1],
                "n_events_total": [1],
                "coverage_pct": [1.0],
                "missing_components": [""],
                "coverage_warning": [""],
                "metric": ["realized_vol"],
                "q_value_fdr": [0.5],
                "sample_warning": [""],
                "window_name": ["pm7"],
                "baseline_method": ["non_event"],
                "effect_minus_baseline": [0.1],
            }
        ),
        runs=pd.DataFrame({"run_type": ["exploratory_formal_batch"], "hypothesis_id": ["H1"]}),
        warnings=["licensing: review required.", "credit_proxy: BAA_MINUS_AAA proxy."],
        run_id="test-run",
        readiness={
            "status": "ready_with_warnings",
            "can_run_exploratory_formal_batch": True,
            "warning_counts": {"licensing": 1},
        },
        config_path="astro_research/configs/research_batch_exploratory_v1.yaml",
        config_hash="a" * 64,
        git_commit="b" * 40,
        git_dirty=True,
        input_fingerprints=[
            {"name": "research_events", "path": "events.parquet", "exists": True, "row_count": 1, "schema_sha256": "c" * 64},
            {"name": "market_daily_features", "path": "market.parquet", "exists": True, "row_count": 1, "schema_sha256": "d" * 64},
            {"name": "research_hypotheses", "path": "hypotheses.parquet", "exists": True, "row_count": 1, "schema_sha256": "e" * 64},
        ],
        run_metadata={"not_publication_grade": True, "association_only": True},
    )

    paths = write_batch_report(batch, tmp_path, config_text="run:\n", hypothesis_snapshot=pd.DataFrame({"hypothesis_id": ["H1"]}))
    manifest = json.loads(paths["run_manifest.json"].read_text())

    assert manifest["manifest_version"] == RUN_MANIFEST_VERSION
    assert manifest["run_id"] == "test-run"
    assert manifest["config"]["sha256"] == "a" * 64
    assert manifest["git"] == {"commit": "b" * 40, "dirty": True}
    assert manifest["readiness"]["status"] == "ready_with_warnings"
    assert {item["name"] for item in manifest["inputs"]} == {"research_events", "market_daily_features", "research_hypotheses"}
    assert {"results.parquet", "event_traceability.csv", "config_snapshot.yaml"}.issubset({item["artifact"] for item in manifest["outputs"]})
    assert validate_exploratory_batch_outputs(tmp_path) == []


def test_batch_summary_uses_readiness_status_without_stale_provenance_caveat(tmp_path):
    batch = BatchStudyResult(
        results=pd.DataFrame(),
        runs=pd.DataFrame({"run_type": ["exploratory_formal_batch"], "hypothesis_id": ["H1"]}),
        warnings=["licensing: review required."],
        run_id="test",
        readiness={
            "status": "ready_with_warnings",
            "can_run_exploratory_formal_batch": True,
            "warning_counts": {"licensing": 1, "credit_proxy": 1},
            "metrics": {"has_local_provenance": True},
        },
    )

    paths = write_batch_report(batch, tmp_path, config_text="run:\n", hypothesis_snapshot=pd.DataFrame({"hypothesis_id": ["H1"]}))
    summary = paths["summary.md"].read_text()

    assert "readiness_status: `ready_with_warnings`" in summary
    assert "Local data provenance is incomplete" not in summary
    assert "credit-proxy warnings" in summary


def test_batch_summary_keeps_provenance_caveat_when_readiness_reports_it(tmp_path):
    batch = BatchStudyResult(
        results=pd.DataFrame(),
        runs=pd.DataFrame({"run_type": ["exploratory_formal_batch"], "hypothesis_id": ["H1"]}),
        warnings=[],
        run_id="test",
        readiness={
            "status": "ready_with_warnings",
            "can_run_exploratory_formal_batch": True,
            "warning_counts": {"provenance": 2},
            "metrics": {"has_local_provenance": True},
        },
    )

    paths = write_batch_report(batch, tmp_path, config_text="run:\n", hypothesis_snapshot=pd.DataFrame({"hypothesis_id": ["H1"]}))
    summary = paths["summary.md"].read_text()

    assert "Local data provenance warnings remain" in summary


def _write_minimal_run_manifest(path: Path) -> None:
    (path / "run_manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": RUN_MANIFEST_VERSION,
                "run_id": "run",
                "config": {"sha256": "a" * 64},
                "git": {"commit": "b" * 40, "dirty": True},
                "inputs": [
                    {"name": "research_events", "schema_sha256": "c" * 64},
                    {"name": "market_daily_features", "schema_sha256": "d" * 64},
                    {"name": "research_hypotheses", "schema_sha256": "e" * 64},
                ],
                "outputs": [
                    {"artifact": "results.parquet"},
                    {"artifact": "event_traceability.csv"},
                    {"artifact": "warnings.json"},
                    {"artifact": "config_snapshot.yaml"},
                ],
            }
        )
    )

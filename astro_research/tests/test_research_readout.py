from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.readout import build_research_readout


def test_research_readout_links_casebook_manifest_and_hypothesis_status(tmp_path: Path):
    casebook = tmp_path / "casebook" / "index.md"
    casebook.parent.mkdir()
    casebook.write_text(
        "\n".join(
            [
                "# Crisis Casebook Index",
                "",
                "| crisis | window | market_stress_peak | financial_stress_daily | astro_event_families | missing_components | caveat_flags | report |",
                "|---|---|---|---|---|---|---|---|",
                "| 2008 GFC | 2008-09-01 to 2009-03-31 | SPX drawdown | rows=10 | mars_saturn_hard_aspect=2 | none | descriptive_only | [r](r.md) |",
                "| 2020 COVID | 2020-02-15 to 2020-04-30 | VIX absret | rows=8 | station_cluster=1 | none | descriptive_only | [r](r.md) |",
            ]
        )
    )
    batch = tmp_path / "batch"
    batch.mkdir()
    pd.DataFrame(
        {
            "hypothesis_id": [
                "H001_station_cluster_stress",
                "H001_station_cluster_stress",
                "H002_mercury_station_volatility",
                "H003_mars_saturn_hard_aspects",
                "H004_macro_core_aspect_cluster",
            ],
            "sample_warning": ["", "insufficient_events", "", "", ""],
            "coverage_warning": ["", "", "partial_coverage", "", "missing_asset"],
        }
    ).to_csv(batch / "results.csv", index=False)
    (batch / "event_study_runs.csv").write_text("run_type\nexploratory_formal_batch\n")
    (batch / "warnings.json").write_text(
        json.dumps(
            {
                "warnings": [
                    {"category": "licensing", "message": "local only"},
                    {"category": "credit_proxy", "message": "proxy only"},
                ],
                "warning_count": 2,
            }
        )
    )
    (batch / "top_findings.md").write_text("No robust findings under current thresholds.\n")
    (batch / "summary.md").write_text("Association only, not causal.\n")
    (batch / "run_manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": "research_run_manifest_v1",
                "run_id": "exploratory_formal_batch_v1_1926_2025",
                "run_type": "exploratory_formal_batch",
                "config": {"sha256": "a" * 64},
                "git": {"commit": "b" * 40, "dirty": True},
                "readiness": {
                    "status": "ready_with_warnings",
                    "can_run_exploratory_formal_batch": True,
                    "warning_counts": {"licensing": 1, "credit_proxy": 1},
                },
                "inputs": [
                    {"name": "research_events", "row_count": 10, "schema_sha256": "c" * 64},
                    {"name": "market_daily_features", "row_count": 20, "schema_sha256": "d" * 64},
                    {"name": "research_hypotheses", "row_count": 4, "schema_sha256": "e" * 64},
                ],
                "outputs": [
                    {"artifact": "results.parquet"},
                    {"artifact": "event_traceability.csv"},
                    {"artifact": "warnings.json"},
                    {"artifact": "config_snapshot.yaml"},
                ],
                "warnings": {"warning_count": 2},
            }
        )
    )

    output = build_research_readout(casebook_index_path=casebook, batch_output_dir=batch, output_path=tmp_path / "out" / "readout.md")
    text = output.read_text()

    assert "crisis_casebook_index | present | cases=2" in text
    assert "run_id=exploratory_formal_batch_v1_1926_2025" in text
    assert "| H001_station_cluster_stress | 2 | 1 | 0 |" in text
    assert "| H002_mercury_station_volatility | 1 | 0 | 1 |" in text
    assert "| H003_mars_saturn_hard_aspects | 1 | 0 | 0 |" in text
    assert "| H004_macro_core_aspect_cluster | 1 | 0 | 1 |" in text
    assert "no_robust_findings_under_current_thresholds: `true`" in text
    assert "readiness_warning_counts: `credit_proxy=1;licensing=1`" in text
    assert "does not assert causality, prediction, investment advice, or a trading signal" in text

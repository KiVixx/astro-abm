from __future__ import annotations

import json

import pandas as pd

from research.formal_readiness import (
    _check_provenance,
    build_formal_readiness,
    readiness_status,
    run_data_quality_checks,
)
from research.source_registry import build_source_registry


def test_provenance_required_fields_warns_for_missing_fields(tmp_path):
    provenance = [{"asset": "SPX", "source": "Yahoo Finance chart endpoint: ^GSPC"}]
    warnings = []

    _check_provenance(provenance=provenance, path=tmp_path / "LOCAL_DATA_PROVENANCE.json", warnings=warnings)

    messages = [warning["message"] for warning in warnings]
    assert any("missing provenance field `original_symbol_or_series`" in message for message in messages)


def test_yahoo_and_lbma_sources_get_licensing_warnings(tmp_path):
    provenance = [
        {"asset": "SPX", "source": "Yahoo Finance chart endpoint: ^GSPC"},
        {"asset": "Gold", "source": "LBMA gold PM USD JSON"},
    ]
    warnings = []

    _check_provenance(provenance=provenance, path=tmp_path / "LOCAL_DATA_PROVENANCE.json", warnings=warnings)

    messages = "\n".join(warning["message"] for warning in warnings)
    assert "Yahoo local_research_only" in messages
    assert "LBMA/ICE licensing_review_required" in messages


def test_baa_aaa_proxy_is_not_mislabeled_as_true_hy_oas(tmp_path):
    provenance = [{"asset": "HY_OAS_PROXY", "source": "FRED Moody's BAA minus AAA corporate yield spread"}]
    warnings = []

    _check_provenance(provenance=provenance, path=tmp_path / "LOCAL_DATA_PROVENANCE.json", warnings=warnings)

    messages = "\n".join(warning["message"] for warning in warnings)
    assert "proxy_type=BAA_MINUS_AAA" in messages
    assert "not_equivalent_to=ICE_BofA_HY_OAS" in messages


def test_data_quality_duplicate_date_and_extreme_return_warning(tmp_path):
    market_config = tmp_path / "market.yaml"
    market_config.write_text(
        """
assets:
  SPX:
    source: "local_csv"
    path: "spx.csv"
"""
    )
    macro_config = tmp_path / "macro.yaml"
    macro_config.write_text("series:\n")
    bars = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-02"], utc=True),
            "asset": ["SPX", "SPX", "SPX"],
            "source": ["local_csv", "local_csv", "local_csv"],
            "close": [100.0, 100.0, 200.0],
        }
    )
    warnings = []

    run_data_quality_checks(
        bars=bars,
        macro=pd.DataFrame(),
        provenance=[{"asset": "SPX"}],
        market_config_path=market_config,
        macro_config_path=macro_config,
        warnings=warnings,
        extreme_return_threshold=0.20,
        long_flat_run_days=10,
    )

    messages = "\n".join(warning["message"] for warning in warnings)
    assert "duplicate_dates=1" in messages
    assert "extreme_one_day_returns" in messages


def test_readiness_gate_status_logic():
    warnings = [{"category": "licensing", "message": "review required"}]
    metrics = {
        "has_spx_long_history": True,
        "has_financial_stress_daily": True,
        "has_local_provenance": True,
        "cross_asset_non_null_ratio": 0.9,
    }

    assert readiness_status(metrics=metrics, warnings=[]) == "ready_for_exploratory_formal_batch"
    assert readiness_status(metrics=metrics, warnings=warnings) == "ready_with_warnings"
    assert readiness_status(metrics={**metrics, "has_spx_long_history": False}, warnings=[]) == "not_ready"
    assert readiness_status(metrics={**metrics, "cross_asset_non_null_ratio": 0.1}, warnings=[]) == "not_ready"


def test_source_registry_local_metadata_flags():
    registry = build_source_registry("astro_research/configs/data_sources.yaml", root=".")
    local_rows = registry.rows[registry.rows["source"] == "local_csv"]

    spx_metadata = local_rows.loc[local_rows["asset"] == "SPX", "metadata"].iloc[0]
    gold_metadata = local_rows.loc[local_rows["asset"] == "Gold", "metadata"].iloc[0]
    credit_metadata = local_rows.loc[local_rows["asset"] == "BAMLH0A0HYM2", "metadata"].iloc[0]

    assert "provider_family=Yahoo" in spx_metadata
    assert "redistribution_allowed=False" in spx_metadata
    assert "provider_family=LBMA_ICE" in gold_metadata
    assert "proxy_type=BAA_MINUS_AAA" in credit_metadata
    assert "not_equivalent_to=ICE_BofA_HY_OAS" in credit_metadata


def test_build_formal_readiness_outputs_reports(tmp_path):
    root = tmp_path
    market = pd.DataFrame(
        {
            "ts": pd.to_datetime(["1929-01-01", "2020-01-01"], utc=True),
            "asset": ["SPX"] * 2,
            "source": ["local_csv"] * 2,
            "drawdown_60d": [-0.1] * 2,
            "realized_vol_20d": [0.2] * 2,
        }
    )
    bars = pd.DataFrame(
        {
            "ts": pd.to_datetime(["1929-01-01", "2020-01-01"], utc=True),
            "asset": ["SPX"] * 2,
            "source": ["local_csv"] * 2,
            "close": [100.0, 200.0],
        }
    )
    macro = pd.DataFrame({"ts": [], "series_id": [], "source": [], "value": []})
    stress = pd.DataFrame(
        {
            "ts": pd.to_datetime(["1929-01-01", "2020-01-01"], utc=True),
            "stress_universe": ["test"] * 2,
            "cross_asset_stress_score": [0.6] * 2,
        }
    )
    market.to_parquet(root / "market.parquet")
    bars.to_parquet(root / "bars.parquet")
    macro.to_parquet(root / "macro.parquet")
    stress.to_parquet(root / "stress.parquet")
    provenance = root / "provenance.json"
    provenance.write_text(json.dumps([{"asset": "SPX", "source": "Yahoo Finance chart endpoint"}]))
    market_config = root / "market.yaml"
    market_config.write_text("assets:\n  SPX:\n    source: \"local_csv\"\n    path: \"spx.csv\"\n")
    macro_config = root / "macro.yaml"
    macro_config.write_text("series:\n")

    result = build_formal_readiness(
        root=root,
        market_features_path="market.parquet",
        market_bars_path="bars.parquet",
        macro_observations_path="macro.parquet",
        financial_stress_path="stress.parquet",
        provenance_path="provenance.json",
        market_config_path="market.yaml",
        macro_config_path="macro.yaml",
        output_markdown_path="readiness.md",
        output_json_path="readiness.json",
    )

    assert result.status in {"ready_with_warnings", "ready_for_exploratory_formal_batch"}
    assert (root / "readiness.md").exists()
    assert (root / "readiness.json").exists()

from __future__ import annotations

import json

import pandas as pd

from research.validation import validate_research_layer


def test_validation_warns_when_local_registry_metadata_is_missing(tmp_path):
    registry = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "source": ["local_csv"],
            "provider": ["LocalCSVProvider"],
            "series_id": ["SP500"],
            "asset": ["SPX"],
            "frequency": ["business_daily"],
            "coverage_start_ts": pd.to_datetime(["1927-12-30"], utc=True),
            "coverage_end_ts": pd.to_datetime(["2020-01-01"], utc=True),
            "is_canonical": [True],
            "requires_api_key": [False],
            "license_note": ["local research only"],
            "source_url": ["local:spx.csv"],
            "metadata": [""],
            "data_version": ["test"],
            "created_at": pd.to_datetime(["2020-01-01"], utc=True),
        }
    )
    registry.to_parquet(tmp_path / "registry.parquet")

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={"data_source_registry": "registry.parquet"},
        output_path=tmp_path / "validation.md",
    )

    assert any("local_csv rows missing metadata" in warning for warning in warnings)


def test_validation_allows_abstract_local_csv_provider_registry_row(tmp_path):
    registry = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "source": ["local_csv"],
            "provider": ["LocalCSVProvider"],
            "series_id": ["SPX_EXTENDED"],
            "asset": ["SPX_EXTENDED"],
            "frequency": ["daily"],
            "coverage_start_ts": [pd.NaT],
            "coverage_end_ts": [pd.NaT],
            "is_canonical": [True],
            "requires_api_key": [False],
            "license_note": ["Local file provenance must be documented per file."],
            "source_url": ["local"],
            "metadata": [""],
            "data_version": ["test"],
            "created_at": pd.to_datetime(["2020-01-01"], utc=True),
        }
    )
    registry.to_parquet(tmp_path / "registry.parquet")

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={"data_source_registry": "registry.parquet"},
        output_path=tmp_path / "validation.md",
    )

    assert warnings == []


def test_validation_warns_for_macro_transform_without_fill_method(tmp_path):
    macro = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "series_id": ["BAMLH0A0HYM2"],
            "source": ["local_csv"],
            "value": [1.0],
            "original_frequency": ["monthly"],
            "transformed_frequency": ["business_daily"],
            "fill_method": ["none"],
            "units": ["percent"],
            "data_version": ["test"],
            "source_note": ["test"],
        }
    )
    macro.to_parquet(tmp_path / "macro.parquet")

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={"macro_daily_observations": "macro.parquet"},
        output_path=tmp_path / "validation.md",
    )

    assert any("transformed frequency rows require explicit fill_method" in warning for warning in warnings)


def test_validation_warns_when_timing_sensitive_tables_lack_available_ts(tmp_path):
    market = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "asset": ["SPX"],
            "source": ["local_csv"],
            "ret_1d": [0.01],
        }
    )
    macro = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "series_id": ["VIXCLS"],
            "source": ["fred"],
            "value": [20.0],
            "original_frequency": ["daily"],
            "transformed_frequency": ["daily"],
            "fill_method": ["none"],
            "units": ["index"],
            "data_version": ["test"],
            "source_note": ["test"],
        }
    )
    market.to_parquet(tmp_path / "market.parquet")
    macro.to_parquet(tmp_path / "macro.parquet")

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={
            "market_daily_features": "market.parquet",
            "macro_daily_observations": "macro.parquet",
        },
        output_path=tmp_path / "validation.md",
    )

    assert any("market_daily_features: available_ts missing" in warning for warning in warnings)
    assert any("macro_daily_observations: available_ts missing" in warning for warning in warnings)
    assert any("macro_daily_observations: observed_ts missing" in warning for warning in warnings)


def test_validation_checks_aspect_event_traceability(tmp_path):
    traceability = pd.DataFrame(
        {
            "hypothesis_id": ["H003_mars_saturn_hard_aspects"],
            "event_family": ["mars_saturn_hard_aspect"],
            "source_table": ["astro_daily_features"],
            "source_event_count": [1],
            "eligible_event_count": [1],
            "primary_event_count": [1],
            "source_event_id_examples": ["x"],
            "source_note": ["test"],
        }
    )
    traceability.to_csv(tmp_path / "event_traceability.csv", index=False)

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={"event_traceability": "event_traceability.csv"},
        output_path=tmp_path / "validation.md",
    )

    assert any("missing astro_aspect_events eligible events" in warning for warning in warnings)


def test_validation_checks_research_run_manifest(tmp_path):
    manifest = {
        "manifest_version": "research_run_manifest_v1",
        "run_id": "run",
        "association_only": True,
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
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest))

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={"research_run_manifest": "run_manifest.json"},
        output_path=tmp_path / "validation.md",
    )

    assert warnings == []


def test_validation_warns_for_incomplete_research_run_manifest(tmp_path):
    manifest = {
        "manifest_version": "research_run_manifest_v1",
        "run_id": "run",
        "association_only": False,
        "config": {"sha256": ""},
        "git": {"commit": ""},
        "inputs": [{"name": "research_events", "schema_sha256": ""}],
        "outputs": [{"artifact": "results.parquet"}],
    }
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest))

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={"research_run_manifest": "run_manifest.json"},
        output_path=tmp_path / "validation.md",
    )

    assert any("missing config sha256" in warning for warning in warnings)
    assert any("missing git commit" in warning for warning in warnings)
    assert any("missing input fingerprint market_daily_features" in warning for warning in warnings)
    assert any("association_only must be true" in warning for warning in warnings)


def test_validation_passes_core_new_audit_fields(tmp_path):
    registry = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "source": ["local_csv"],
            "provider": ["LocalCSVProvider"],
            "series_id": ["SP500"],
            "asset": ["SPX"],
            "frequency": ["business_daily"],
            "coverage_start_ts": pd.to_datetime(["1927-12-30"], utc=True),
            "coverage_end_ts": pd.to_datetime(["2020-01-01"], utc=True),
            "is_canonical": [True],
            "requires_api_key": [False],
            "license_note": ["local research only"],
            "source_url": ["local:spx.csv"],
            "metadata": ["redistribution_allowed=False;publication_grade=False;is_proxy=False"],
            "data_version": ["test"],
            "created_at": pd.to_datetime(["2020-01-01"], utc=True),
        }
    )
    macro = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "observed_ts": pd.to_datetime(["2020-01-01"], utc=True),
            "available_ts": pd.to_datetime(["2020-01-02"], utc=True),
            "series_id": ["BAMLH0A0HYM2"],
            "source": ["local_csv"],
            "value": [1.0],
            "original_frequency": ["monthly"],
            "transformed_frequency": ["business_daily"],
            "fill_method": ["business_daily_forward_fill"],
            "units": ["percent"],
            "data_version": ["test"],
            "source_note": ["test"],
        }
    )
    coverage = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01"], utc=True),
            "asset": ["BAMLH0A0HYM2"],
            "source": ["local_csv"],
            "coverage_start_ts": pd.to_datetime(["2020-01-01"], utc=True),
            "coverage_end_ts": pd.to_datetime(["2020-01-01"], utc=True),
            "observation_count": [1],
            "missing_count": [0],
            "missing_pct": [0.0],
            "calendar_expected_count": [1],
            "calendar_missing_count": [0],
            "frequency_adjusted_expected_count": [1],
            "frequency_adjusted_missing_count": [0],
            "frequency_adjusted_missing_pct": [0.0],
            "first_valid_ts": pd.to_datetime(["2020-01-01"], utc=True),
            "last_valid_ts": pd.to_datetime(["2020-01-01"], utc=True),
            "frequency": ["business_daily"],
            "data_version": ["test"],
            "source_note": ["test"],
        }
    )
    traceability = pd.DataFrame(
        {
            "hypothesis_id": ["H003_mars_saturn_hard_aspects"],
            "event_family": ["mars_saturn_hard_aspect"],
            "source_table": ["astro_aspect_events"],
            "source_event_count": [1],
            "eligible_event_count": [1],
            "primary_event_count": [1],
            "source_event_id_examples": ["a"],
            "source_note": ["test"],
        }
    )
    registry.to_parquet(tmp_path / "registry.parquet")
    macro.to_parquet(tmp_path / "macro.parquet")
    coverage.to_parquet(tmp_path / "coverage.parquet")
    traceability.to_csv(tmp_path / "trace.csv", index=False)

    _, warnings = validate_research_layer(
        root=tmp_path,
        paths={
            "data_source_registry": "registry.parquet",
            "macro_daily_observations": "macro.parquet",
            "macro_series_coverage": "coverage.parquet",
            "event_traceability": "trace.csv",
        },
        output_path=tmp_path / "validation.md",
    )

    assert warnings == []

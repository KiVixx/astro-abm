from __future__ import annotations

from research.source_registry import build_source_registry


def test_source_registry_builds_rows():
    registry = build_source_registry("astro_research/configs/data_sources.yaml")

    assert "DGS10" in set(registry.rows["series_id"])
    assert registry.rows["requires_api_key"].isin([True, False]).all()


def test_local_source_registry_metadata_includes_provenance_flags():
    registry = build_source_registry("astro_research/configs/data_sources.yaml", root=".")
    local = registry.rows[(registry.rows["source"] == "local_csv") & (registry.rows["asset"] == "SPX")].iloc[0]

    assert "provider_family=Yahoo" in local["metadata"]
    assert "upstream_provider=Yahoo Finance" in local["metadata"]
    assert "redistribution_allowed=False" in local["metadata"]
    assert "publication_grade=False" in local["metadata"]

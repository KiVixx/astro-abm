from __future__ import annotations

from research.source_registry import build_source_registry


def test_source_registry_builds_rows():
    registry = build_source_registry("astro_research/configs/data_sources.yaml")

    assert "DGS10" in set(registry.rows["series_id"])
    assert registry.rows["requires_api_key"].isin([True, False]).all()

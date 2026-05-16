from __future__ import annotations

from research.hypotheses import register_hypotheses


def test_hypothesis_config_hash_is_deterministic():
    first = register_hypotheses("astro_research/configs/research_hypotheses.yaml", git_commit="test")
    second = register_hypotheses("astro_research/configs/research_hypotheses.yaml", git_commit="test")

    assert first.config_hash == second.config_hash
    assert "H001_station_cluster_stress" in set(first.rows["hypothesis_id"])

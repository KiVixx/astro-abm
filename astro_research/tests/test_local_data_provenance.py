from __future__ import annotations

from pathlib import Path

from research.formal_readiness import _check_provenance, _load_provenance


def test_local_data_provenance_manifest_covers_required_local_series():
    path = Path("astro_research/data/local/LOCAL_DATA_PROVENANCE.json")

    provenance = _load_provenance(path)
    labels = {item.get("asset") for item in provenance}

    assert {"SPX", "Gold", "DXY", "HY_OAS_PROXY"}.issubset(labels)


def test_local_data_provenance_manifest_has_required_fields_without_absolute_paths():
    path = Path("astro_research/data/local/LOCAL_DATA_PROVENANCE.json")

    provenance = _load_provenance(path)
    warnings = []
    _check_provenance(provenance=provenance, path=path, warnings=warnings)

    messages = [warning["message"] for warning in warnings]
    assert not [message for message in messages if "missing provenance field" in message]
    assert not any(str(item.get("local_path", "")).startswith("/") for item in provenance)


def test_credit_proxy_provenance_is_explicitly_proxy_not_canonical_hy_oas():
    path = Path("astro_research/data/local/LOCAL_DATA_PROVENANCE.json")

    provenance = _load_provenance(path)
    credit = next(item for item in provenance if item.get("asset") == "HY_OAS_PROXY")

    assert credit["is_proxy"] is True
    assert credit["is_canonical"] is False
    assert credit["proxy_type"] == "BAA_MINUS_AAA"
    assert credit["not_equivalent_to"] == "ICE_BofA_HY_OAS"

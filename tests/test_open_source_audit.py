from astro_abm.analysis.open_source_audit import (
    HISTORY_SECRET_FIXTURE_PATHS,
    allowed_tracked_path,
    secret_categories,
)


def test_secret_categories_detect_values_without_returning_them() -> None:
    value = b"ASTRO_ABM_LLM_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"

    assert secret_categories(value) == ["llm_assignment", "openai_style_key"]
    assert all("abcdefghijklmnopqrstuvwxyz" not in category for category in secret_categories(value))


def test_open_source_audit_allows_only_documented_local_examples() -> None:
    assert allowed_tracked_path(".env.example")
    assert allowed_tracked_path("astro_research/data/local/examples/spx_daily.example.csv")
    assert allowed_tracked_path("astro_research/data/local/LOCAL_DATA_PROVENANCE.json")
    assert not allowed_tracked_path(".env")
    assert not allowed_tracked_path("astro_research/data/local/equity/spx_daily.csv")


def test_history_scan_excludes_only_the_dedicated_secret_fixture() -> None:
    assert HISTORY_SECRET_FIXTURE_PATHS == frozenset({"tests/test_open_source_audit.py"})

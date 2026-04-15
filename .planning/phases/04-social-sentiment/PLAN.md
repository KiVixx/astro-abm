# Phase 4 Plan — Social Sentiment Validation Layer

Goal: Add Python modules for LunarCrush-based hourly social volume and sentiment features.

Requirements covered:
- SENT-01
- SENT-02
- SENT-03

## Work Package 1 — Add failing tests

Files:
- Create: `tests/test_social_sentiment.py`

Steps:
1. Write tests for parsing a LunarCrush asset payload with hourly `timeSeries` data.
2. Write tests for unix timestamp to UTC hour normalization.
3. Write tests for aligned feature-row shaping into `abm_hourly_facts`-style rows.
4. Run tests and confirm failure before implementation.

Success criteria:
- Tests fail because Phase 4 modules do not exist yet.

## Work Package 2 — Implement LunarCrush client and normalization

Files:
- Create: `src/astro_abm/features/social_sentiment.py`

Steps:
1. Implement a small LunarCrush client with API-key based requests.
2. Implement defensive payload parsing for asset/time-series structures.
3. Normalize hourly social metrics into typed rows.
4. Build feature-row shaping for `social_volume`, `sentiment_score`, and optional supporting metrics.

Success criteria:
- Tests pass for parsing and feature-row generation.

## Work Package 3 — Update docs and state

Files:
- Modify: `README.md`
- Modify: `.planning/STATE.md`
- Modify: `src/astro_abm/features/__init__.py`

Steps:
1. Document LunarCrush env/config usage.
2. Export the new feature client from the features package.
3. Update project state after tests pass.

Success criteria:
- Repo clearly describes the Phase 4 social-sentiment layer.

## Verification

- `pytest tests/test_social_sentiment.py -q`
- `pytest -q`

## Notes

- Use strict TDD.
- Keep parsing schema-tolerant and preserve raw-ish semantics through explicit field names.

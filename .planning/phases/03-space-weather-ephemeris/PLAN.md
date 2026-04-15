# Phase 3 Plan — Space Weather & Ephemeris Feature Layer

Goal: Add Python modules for NOAA SWPC ingestion and local ephemeris-based hourly feature computation.

Requirements covered:
- SWTH-01
- SWTH-02
- SWTH-03
- SWTH-04
- SWTH-05
- EPH-01
- EPH-02
- EPH-03

## Work Package 1 — Add failing tests for parser and feature behavior

Files:
- Create: `tests/test_space_weather.py`
- Create: `tests/test_ephemeris.py`

Steps:
1. Write tests for parsing NOAA plasma and mag header-row feeds.
2. Write tests for filtering/parsing GOES X-ray object feeds.
3. Write tests for Kp 3-hour values expanded to hourly timestamps.
4. Write tests for moon phase percentage from a fake Swiss Ephemeris adapter.
5. Write tests for pairwise angular feature computation.
6. Run tests and confirm failure before implementation.

Success criteria:
- Tests fail because Phase 3 modules do not exist yet.

## Work Package 2 — Implement space weather client and row shaping

Files:
- Create: `src/astro_abm/features/__init__.py`
- Create: `src/astro_abm/features/space_weather.py`

Steps:
1. Implement NOAA response parsing helpers.
2. Implement Kp hourly alignment helper.
3. Implement normalized feature-row builder for aligned hourly facts.
4. Keep source metadata explicit (`noaa_swpc`).

Success criteria:
- Tests pass for parsing and hourly feature generation.

## Work Package 3 — Implement local ephemeris calculator

Files:
- Create: `src/astro_abm/features/ephemeris.py`

Steps:
1. Implement UTC datetime to Julian day conversion.
2. Implement planetary longitude retrieval through injectable `swisseph` adapter.
3. Implement moon phase percentage calculation.
4. Implement relative angular feature generation for major planets.
5. Implement aligned feature-row builder for `GLOBAL` features.

Success criteria:
- Tests pass for moon phase and angular feature generation.

## Work Package 4 — Document and update project state

Files:
- Modify: `README.md`
- Modify: `.planning/STATE.md`
- Modify: `pyproject.toml`

Steps:
1. Add `pyswisseph` dependency/config note.
2. Document Phase 3 module responsibilities and feature sources.
3. Update state to Phase 3 complete after tests pass.

Success criteria:
- Repo documents where space-weather and ephemeris features come from and how they are computed.

## Verification

- `pytest tests/test_space_weather.py -q`
- `pytest tests/test_ephemeris.py -q`
- `pytest -q`

## Notes

- Use strict TDD.
- Keep the Swiss Ephemeris integration injectable so tests do not depend on live astronomy files.

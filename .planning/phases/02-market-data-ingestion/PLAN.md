# Phase 2 Plan — Financial Market Data Ingestion (1H OHLCV)

Goal: Add Python ingestion code for hourly crypto and tradfi bars plus a QuestDB write path.

Requirements covered:
- CRYP-01
- CRYP-02
- CRYP-03
- TRAD-01
- TRAD-02

## Work Package 1 — Establish Python project skeleton

Files:
- Create: `pyproject.toml`
- Create: `src/astro_abm/__init__.py`
- Create: `src/astro_abm/config.py`
- Create: `tests/`

Steps:
1. Add a minimal Python package layout under `src/astro_abm`.
2. Add project/dependency metadata for requests, python-binance, and pytest.
3. Add config helpers for provider API keys and QuestDB connection settings.

Success criteria:
- The repo has a coherent Python package structure for the ingestion modules.

## Work Package 2 — Add failing tests for normalization and writing

Files:
- Create: `tests/test_market_data.py`

Steps:
1. Write tests for Binance 1-hour normalization from raw kline rows.
2. Write tests for Polygon response normalization.
3. Write tests for Alpha Vantage response normalization.
4. Write tests for QuestDB writer batch insert behavior.
5. Run tests and confirm failure before implementation.

Success criteria:
- Tests fail because production modules do not exist yet.

## Work Package 3 — Implement provider clients and normalized bar model

Files:
- Create: `src/astro_abm/models.py`
- Create: `src/astro_abm/market_data/__init__.py`
- Create: `src/astro_abm/market_data/binance_client.py`
- Create: `src/astro_abm/market_data/tradfi.py`
- Create: `src/astro_abm/storage/questdb.py`

Steps:
1. Add a normalized `MarketBar` model.
2. Implement Binance spot hourly fetch/normalize logic.
3. Implement Polygon hourly fetch/normalize logic.
4. Implement Alpha Vantage hourly parse/normalize logic.
5. Implement QuestDB writer for `market_ohlcv_1h` using PG-wire compatible SQL execution.

Success criteria:
- Tests pass using stubbed dependencies.
- Code supports BTCUSDT and SPY as initial symbols.

## Work Package 4 — Document usage and phase status

Files:
- Modify: `README.md`
- Modify: `.planning/STATE.md`

Steps:
1. Document env vars and module responsibilities.
2. Explain chosen tradfi default provider.
3. Update state file to reflect Phase 2 implementation progress.

Success criteria:
- A developer can discover how to configure and invoke Phase 2 modules.

## Verification

- `pytest -q`
- Optional later, with credentials configured:
  - live fetch for BTCUSDT via Binance
  - live fetch for SPY via Polygon

## Notes

- Use strict TDD.
- Avoid live API calls in tests.
- Keep normalization timezone-safe and explicit.

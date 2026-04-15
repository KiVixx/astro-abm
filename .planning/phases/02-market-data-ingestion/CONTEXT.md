# Phase 2 Context — Financial Market Data Ingestion (1H OHLCV)

## Goal

Implement the first production-facing Python ingestion layer for hourly crypto and tradfi market bars, normalize both sources onto the shared UTC hourly schema, and provide a QuestDB write path for storing the results.

## Scope

In scope:
- Python project structure for market data ingestion
- Binance hourly crypto ingestion via `python-binance`
- Tradfi hourly provider abstraction with Polygon default and Alpha Vantage fallback/parser support
- Normalized bar model shared across providers
- QuestDB write path for `market_ohlcv_1h`
- Tests for provider normalization and write behavior

Out of scope:
- APScheduler orchestration
- Space weather ingestion
- Ephemeris computation
- Social sentiment ingestion
- Full ETL alignment/fill policy beyond bar normalization

## Key Constraints

- All returned bars must normalize to UTC hour-bucket start timestamps.
- Crypto ingestion must use `Client.KLINE_INTERVAL_1HOUR`.
- Tradfi provider implementation must support SPY first and be extensible to defensive-sector tickers.
- QuestDB writes should preserve `observed_ts`, `available_ts`, and source metadata.
- Repo is currently nearly empty, so Phase 2 must establish a sane Python project layout.

## Assumptions

- Network credentials will be supplied later via environment variables.
- Polygon is the preferred tradfi provider; Alpha Vantage is supported as a fallback normalization path.
- Unit tests should avoid live network calls and use stubs/fakes.

## Acceptance Expectations

- Project contains tested Python modules for Binance and tradfi provider ingestion.
- A developer can read config/env requirements and understand how to fetch 1-hour bars.
- QuestDB writer accepts normalized bars and targets `market_ohlcv_1h`.

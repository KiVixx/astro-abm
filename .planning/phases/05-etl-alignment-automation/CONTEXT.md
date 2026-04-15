# Phase 5 Context — ETL Alignment & Automation

## Goal

Implement the orchestration layer that takes hourly data from the completed source modules, aligns everything on a UTC hourly timeline, applies tradfi forward fill where appropriate, and schedules the ETL to run automatically each hour at minute 05.

## Scope

In scope:
- UTC normalization helpers for heterogeneous hourly inputs
- Tradfi forward-fill logic over aligned hourly ranges
- Multi-source feature/market DataFrame merging
- Conversion of aligned DataFrames into row batches for QuestDB writers
- APScheduler-based hourly ETL scheduling factory

Out of scope:
- New external data providers
- Full production service packaging / deployment
- Historical backfill orchestration beyond reusable ETL helpers

## Key Constraints

- All aligned outputs must use UTC hour-bucket start timestamps.
- TradFi gaps may be forward-filled, but crypto / astro / social features should preserve missingness unless explicitly present.
- ETL scheduler must be testable without starting background threads in unit tests.
- Existing phase modules should remain reusable and loosely coupled.

## Assumptions

- Pandas will be used for alignment and merge operations.
- APScheduler BackgroundScheduler is acceptable for embedded/in-process scheduling.
- Phase 2/3/4 modules can provide normalized rows or DataFrames to the alignment layer.

## Acceptance Expectations

- Repo contains tested helpers for UTC alignment, tradfi forward fill, and merged hourly feature frames.
- Repo contains a scheduler factory that wires one hourly ETL job at minute 05 UTC.
- The ETL layer is ready to be connected to live data fetchers and QuestDB writes.

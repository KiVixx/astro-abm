# Astro ABM

## What This Is

Astro ABM is a multi-agent simulation platform that models financial market behavior through a non-traditional sentiment perturbation layer derived from astronomy and space weather signals. The MVP focuses on building a robust 1-hour UTC-aligned data pipeline that combines crypto market data, traditional market data, space weather indicators, ephemeris-derived features, and social sentiment for downstream agent-based modeling.

## Core Value

Create a reproducible hourly feature pipeline that lets the system test whether exogenous astro/space-weather signals can explain or perturb simulated market sentiment and agent behavior.

## Requirements

### Validated

(None yet — MVP initialization)

### Active

- [ ] Build QuestDB-backed time-series storage for unified 1-hour data.
- [ ] Ingest 1-hour crypto OHLCV for high-volatility assets such as BTCUSDT.
- [ ] Ingest 1-hour tradfi benchmark OHLCV for SPY and defensive sectors.
- [ ] Ingest and align NOAA SWPC space-weather signals to hourly UTC buckets.
- [ ] Compute local ephemeris-derived hourly astro features with pyswisseph.
- [ ] Ingest hourly LunarCrush social volume and sentiment features.
- [ ] Normalize all pipelines to UTC and support downstream forward-fill logic where appropriate.
- [ ] Automate hourly ETL writes into QuestDB via APScheduler.

### Out of Scope

- Minute-level or tick-level ingestion — intentionally deferred to reduce MVP noise.
- Full agent decision engine implementation — deferred until the hourly data foundation is stable.
- Strategy alpha claims or live trading execution — not part of infrastructure MVP.

## Context

The system blends objective astronomical and space-weather measurements with financial and social signals. Two target agent populations are planned: retail swarm clusters and LLM-driven Fortune 500 CEOs. The present milestone is infrastructure-first: enforce a single hourly UTC timeline and preserve data provenance with observation and availability timestamps to avoid future look-ahead leakage.

## Constraints

- **Temporal Resolution**: All MVP datasets must be aligned to 1-hour UTC buckets.
- **Database**: QuestDB is the primary time-series store for aligned facts and OHLCV.
- **Astro Computation**: Ephemeris calculations must be local via pyswisseph, not external APIs.
- **Reproducibility**: Raw/aligned timestamps and source metadata must be preserved.
- **Scope Control**: Build the data layer before implementing the ABM behavior layer.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use QuestDB for aligned hourly storage | Fast time-series ingestion/query with SQL and SYMBOL optimizations | — Pending |
| Standardize all tables on UTC hour-bucket `ts` | Necessary to join heterogeneous markets and exogenous signals | — Pending |
| Preserve `observed_ts` and `available_ts` alongside aligned `ts` | Reduces risk of future leakage in modeling/backtests | — Pending |
| Keep a unified hourly facts table plus a dedicated OHLCV table | Balances flexible feature ingestion with efficient bar queries | — Pending |

---
*Last updated: 2026-04-15 after GSD initialization*

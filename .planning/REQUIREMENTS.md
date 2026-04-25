# Requirements: Astro ABM

**Defined:** 2026-04-15
**Core Value:** Create a reproducible hourly feature pipeline that lets the system test whether exogenous astro/space-weather signals can explain or perturb simulated market sentiment and agent behavior.

## v1 Requirements

### Infrastructure

- [ ] **INF-01**: System can run QuestDB locally via Docker with persistent storage.
- [ ] **INF-02**: System defines QuestDB schemas with `ts` as designated timestamp and monthly partitions.
- [ ] **INF-03**: Core aligned fact storage uses SYMBOL columns for repeated categorical dimensions.

### Crypto Market Data

- [ ] **CRYP-01**: System ingests 1-hour BTCUSDT OHLCV from Binance.
- [ ] **CRYP-02**: System supports adding more high-volatility crypto symbols with the same pipeline.
- [ ] **CRYP-03**: Crypto bars are persisted with provenance timestamps and completion state.

### TradFi Market Data

- [ ] **TRAD-01**: System ingests 1-hour SPY data from Polygon.io or Alpha Vantage.
- [ ] **TRAD-02**: System supports key defensive-sector instruments as additional tradfi symbols.
- [ ] **TRAD-03**: Missing tradfi hours can be forward-filled in aligned downstream datasets.

### Space Weather

- [ ] **SWTH-01**: System ingests NOAA SWPC JSON data for solar wind speed.
- [ ] **SWTH-02**: System ingests NOAA SWPC JSON data for IMF Bz.
- [ ] **SWTH-03**: System ingests NOAA SWPC JSON data for X-ray flux.
- [ ] **SWTH-04**: System ingests NOAA SWPC JSON data for Kp index.
- [ ] **SWTH-05**: Kp values are aggregated or expanded into 1-hour aligned UTC buckets.

### Ephemeris

- [ ] **EPH-01**: System computes hourly moon-phase percentage locally via pyswisseph.
- [ ] **EPH-02**: System computes hourly major-planet relative angular/gravity proxy features locally.
- [ ] **EPH-03**: Ephemeris features are generated directly from UTC timestamps without external APIs.

### Social Sentiment

- [ ] **SENT-01**: System ingests hourly LunarCrush social volume features.
- [ ] **SENT-02**: System ingests hourly LunarCrush sentiment score features.
- [ ] **SENT-03**: Social features can be linked to crypto asset symbols on the shared hourly timeline.

### ETL Alignment & Scheduling

- [ ] **ETL-01**: All data sources are normalized to UTC.
- [ ] **ETL-02**: All aligned outputs use a consistent 1-hour bucket start timestamp.
- [ ] **ETL-03**: ETL pipeline writes Pandas DataFrames into QuestDB in batch form.
- [ ] **ETL-04**: APScheduler runs all hourly collection jobs at minute 05 of each hour.
- [ ] **ETL-05**: Pipeline preserves `observed_ts` and `available_ts` where meaningful.

## v2 Requirements

### ABM Simulation

- **ABM-01**: Retail swarm agents react to aligned sentiment perturbation variables.
- **ABM-02**: CEO agents use aligned market and macro/emotional features for decision steps.
- **ABM-03**: Simulation engine can replay historical aligned data windows.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Minute-level ingestion | Deferred to keep MVP tractable and reduce noise |
| Live trade execution | Not part of infrastructure MVP |
| Full LLM-driven agent orchestration | Deferred until hourly feature pipeline is stable |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INF-01 | Phase 1 | Implemented; local QuestDB runtime validated |
| INF-02 | Phase 1 | Implemented; unit-reviewed via schema file |
| INF-03 | Phase 1 | Implemented; unit-reviewed via schema file |
| CRYP-01 | Phase 2 | Scaffolded and unit-tested; live Binance run pending |
| CRYP-02 | Phase 2 | Scaffolded and unit-tested |
| CRYP-03 | Phase 2 | Writer implemented and unit-tested; live market-bar write pending |
| TRAD-01 | Phase 2 | Scaffolded and unit-tested; credentials pending |
| TRAD-02 | Phase 2 | Scaffolded and unit-tested |
| TRAD-03 | Phase 5 | Implemented and unit-tested |
| SWTH-01 | Phase 3 | Parser/client scaffold implemented and unit-tested |
| SWTH-02 | Phase 3 | Parser/client scaffold implemented and unit-tested |
| SWTH-03 | Phase 3 | Parser/client scaffold implemented and unit-tested |
| SWTH-04 | Phase 3 | Parser/client scaffold implemented and unit-tested |
| SWTH-05 | Phase 3 | Implemented and unit-tested |
| EPH-01 | Phase 3 | Implemented and unit-tested |
| EPH-02 | Phase 3 | Implemented and unit-tested |
| EPH-03 | Phase 3 | Implemented and unit-tested |
| SENT-01 | Phase 4 | Scaffolded and unit-tested; credentials pending |
| SENT-02 | Phase 4 | Scaffolded and unit-tested; credentials pending |
| SENT-03 | Phase 4 | Implemented and unit-tested |
| ETL-01 | Phase 5 | Implemented and unit-tested |
| ETL-02 | Phase 5 | Implemented and unit-tested |
| ETL-03 | Phase 5 | Implemented and unit-tested |
| ETL-04 | Phase 5 | Implemented and unit-tested |
| ETL-05 | Phase 5 | Implemented and unit-tested |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-04-15*
*Last updated: 2026-04-25 after live ETL skeleton, QuestDB fact writer, and local QuestDB smoke test*

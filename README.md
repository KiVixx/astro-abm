# Astro ABM

Astro ABM is an hourly data-engineering foundation for a future agent-based market simulator.

The core hypothesis is intentionally unconventional:

- objective astronomy and space-weather signals can be transformed into exogenous sentiment-perturbation variables
- those variables may help explain changes in market risk appetite
- the effect can be studied across two future agent populations:
  - a retail swarm in high-volatility crypto markets
  - more deliberate corporate/CEO-style decision agents in traditional finance

This repository does not yet contain the full simulation engine.

What it does contain is the MVP data-layer scaffold required before any meaningful ABM work can start:

- QuestDB storage schema and local runtime config
- hourly market-data provider modules
- hourly space-weather parsing helpers
- local ephemeris feature computation helpers
- hourly crypto social-sentiment parsing helpers
- ETL alignment and scheduling helpers

The entire MVP is standardized around a single rule:

All features must align to UTC 1-hour buckets.

--------------------------------------------------
## Current Status

Implemented and unit-tested:

- Phase 1 — QuestDB setup and schema
- Phase 2 — crypto + tradfi market-data provider and normalization skeleton
- Phase 3 — NOAA SWPC parsing helpers + local ephemeris feature layer
- Phase 4 — LunarCrush social-sentiment parsing layer
- Phase 5 — ETL alignment helpers, tradfi forward-fill placeholder, scheduler wiring

Current test status:

```bash
pytest -q
# 19 passed
```

Not yet implemented:

- one end-to-end live ETL entrypoint that wires all providers together
- credential/bootstrap automation like `.env.example`
- ABM simulation runtime and agent logic
- model training / validation workflows

--------------------------------------------------
## Why this repository exists

The long-term system needs to answer a hard question:

Can astro / space-weather conditions be represented as measurable perturbations to sentiment, and can those perturbations be aligned against financial and social data strongly enough to justify agent-based simulation experiments?

Before testing that, the system needs a disciplined feature store.

That is the purpose of this repo.

It defines the building blocks for a reproducible hourly pipeline where the following can eventually be compared on the same timeline:

- crypto OHLCV
- tradfi OHLCV
- solar-wind / IMF / X-ray / Kp activity
- moon phase and planetary angular features
- crypto social volume and sentiment

--------------------------------------------------
## Design Principles

### 1. One canonical time axis
Every source is normalized to:

- UTC
- bucket start timestamps
- 1-hour resolution

Example:

`2024-04-15T15:00:00Z` means the interval from 15:00:00 to 15:59:59 UTC.

### 2. Provenance matters
Wherever possible, rows preserve:

- `ts` — aligned hourly timestamp
- `observed_ts` — when the underlying event or measurement happened
- `available_ts` — when it became available to the pipeline

This is important for later leakage control in backtests or predictive models.

### 3. Separate raw source logic from alignment logic
Each provider module is responsible for:

- fetching source data
- parsing source payloads
- normalizing into internal row structures

The ETL layer is responsible for:

- UTC conversion
- forward fill policy
- frame merging
- row shaping for QuestDB

### 4. Build the data layer before the simulation layer
The repo intentionally prioritizes reliable hourly features over premature agent behavior code.

--------------------------------------------------
## Repository Structure

```text
astro-abm/
├── docker-compose.questdb.yml
├── pyproject.toml
├── README.md
├── sql/
│   └── schema_phase1.sql
├── src/astro_abm/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── market_data/
│   │   ├── __init__.py
│   │   ├── binance_client.py
│   │   └── tradfi.py
│   ├── features/
│   │   ├── __init__.py
│   │   ├── ephemeris.py
│   │   ├── social_sentiment.py
│   │   └── space_weather.py
│   ├── storage/
│   │   ├── __init__.py
│   │   └── questdb.py
│   └── etl/
│       ├── __init__.py
│       ├── pipeline.py
│       └── scheduler.py
├── tests/
│   ├── test_market_data.py
│   ├── test_space_weather.py
│   ├── test_ephemeris.py
│   ├── test_social_sentiment.py
│   └── test_etl.py
└── .planning/
    ├── PROJECT.md
    ├── REQUIREMENTS.md
    ├── ROADMAP.md
    ├── STATE.md
    └── phases/
```

--------------------------------------------------
## Data Model and Storage

### QuestDB runtime
Start QuestDB locally:

```bash
docker compose -f docker-compose.questdb.yml up -d
```

Stop it:

```bash
docker compose -f docker-compose.questdb.yml down
```

Ports:

- `9000` → QuestDB Web Console / HTTP
- `8812` → PostgreSQL wire protocol
- `9009` → ILP TCP ingest

Web UI:

- http://localhost:9000

### Schema file
SQL lives at:

- `sql/schema_phase1.sql`

### Core tables

#### `abm_hourly_facts`
Unified hourly feature table for non-OHLCV features and flexible aligned facts.

Intended uses:

- space weather metrics
- ephemeris metrics
- social sentiment metrics
- other future hourly exogenous features

#### `market_ohlcv_1h`
Dedicated hourly OHLCV table for market bars.

Intended uses:

- crypto market bars
- tradfi market bars
- more efficient retrieval of bar data than storing OHLCV entirely in key-value feature rows

#### `abm_entities`
Optional metadata dictionary for symbols / entities.

### Timestamp semantics

- `ts` = UTC 1-hour bucket start and QuestDB designated timestamp
- `observed_ts` = when the underlying measurement/bar/event was observed
- `available_ts` = when the value became available to the pipeline

This separation is deliberate so later modeling code can avoid accidental look-ahead bias.

--------------------------------------------------
## Implemented Features by Phase

## Phase 1 — Database & Infrastructure Foundation

Files:

- `docker-compose.questdb.yml`
- `sql/schema_phase1.sql`

What it provides:

- local QuestDB startup
- monthly-partitioned hourly storage schema
- extensive use of `SYMBOL` fields for repeated categorical dimensions

Why it matters:

Without a stable hourly store, every later modeling step becomes ad hoc and irreproducible.

--------------------------------------------------
## Phase 2 — Financial Market Data Ingestion (1H OHLCV)

Files:

- `src/astro_abm/models.py`
- `src/astro_abm/market_data/binance_client.py`
- `src/astro_abm/market_data/tradfi.py`
- `src/astro_abm/storage/questdb.py`

### Normalized model: `MarketBar`
`MarketBar` is the project’s internal representation for one hourly market candle.

It captures:

- symbol
- ts
- open / high / low / close / volume
- source / venue / market_type / asset_class
- optional quote volume, trade count, vwap
- observed / available timestamps

### Crypto ingestion: Binance
Module:

- `src/astro_abm/market_data/binance_client.py`

What it does:

- uses `python-binance`
- requests 1-hour bars via `Client.KLINE_INTERVAL_1HOUR`
- normalizes Binance kline arrays into `MarketBar`

Current scope:

- tested for hourly normalization behavior
- suitable as the crypto provider skeleton for BTCUSDT and similar symbols

### TradFi ingestion: Polygon + Alpha Vantage
Module:

- `src/astro_abm/market_data/tradfi.py`

What it does:

- `PolygonProvider`
  - normalizes aggregate bars into `MarketBar`
  - intended as the default tradfi provider
- `AlphaVantageProvider`
  - parses `TIME_SERIES_INTRADAY` 60-minute payloads
  - converts provider-local timestamps to UTC

Why two providers:

- Polygon is the cleaner default for hourly bars
- Alpha Vantage provides a fallback / alternate parser path

### QuestDB market writer
Module:

- `src/astro_abm/storage/questdb.py`

What it does:

- `QuestDBMarketBarWriter`
- converts `MarketBar` objects into batched inserts for `market_ohlcv_1h`
- uses PG-wire via `psycopg`

--------------------------------------------------
## Phase 3 — Space Weather & Ephemeris Feature Layer

Files:

- `src/astro_abm/features/space_weather.py`
- `src/astro_abm/features/ephemeris.py`

### Space weather parsing and row shaping
Module:

- `space_weather.py`

NOAA SWPC sources used:

- solar-wind plasma 1-day JSON
- magnetometer 1-day JSON
- GOES primary X-ray JSON
- planetary K-index JSON

What it does:

- parses NOAA header-row table feeds
- parses X-ray object feeds
- filters X-ray data to the `0.1-0.8nm` channel
- expands 3-hour Kp values into hourly buckets
- shapes feature rows for the unified hourly facts table

Key helper:

- `build_space_weather_feature_rows()`

Current supported metrics:

- `solar_wind_speed`
- `imf_bz`
- `xray_flux`
- `kp_index`

### Local ephemeris computation
Module:

- `ephemeris.py`

What it does:

- converts UTC datetime to Julian day
- computes planetary positions through injectable `swisseph`
- derives moon phase percentage from Sun/Moon elongation
- derives relative angular features between major planets
- shapes feature rows for `abm_hourly_facts`

Why the dependency is injectable:

Tests should not depend on local ephemeris files or live Swiss Ephemeris state.

Current feature examples:

- `moon_phase_pct`
- `moon_is_waxing`
- `sun_moon_angle_abs`
- `sun_moon_angle_signed`
- `mars_jupiter_angle_abs`
- `mars_jupiter_angle_signed`

--------------------------------------------------
## Phase 4 — Social Sentiment Validation Layer

File:

- `src/astro_abm/features/social_sentiment.py`

What it does:

- defines `LunarCrushClient`
- parses asset-level hourly social payloads
- normalizes unix timestamps to UTC hour buckets
- shapes social feature rows for the unified hourly facts table

Current supported metrics:

- `social_volume`
- `sentiment_score`
- `social_contributors`
- `average_sentiment`
- `social_dominance`

Why this layer exists:

This is the first calibration / validation layer against the astro hypothesis.

The idea is not that social sentiment replaces astro features.
The idea is that social sentiment can later be used to test whether astro-derived perturbation variables appear to line up with observable crowd behavior.

--------------------------------------------------
## Phase 5 — ETL Alignment & Automation

Files:

- `src/astro_abm/etl/pipeline.py`
- `src/astro_abm/etl/scheduler.py`

### ETL pipeline helpers
Module:

- `pipeline.py`

What it does:

- `normalize_to_utc_hour()`
  - converts heterogeneous timestamps to UTC
  - floors to bucket start

- `align_tradfi_hourly()`
  - expands missing tradfi hourly bars across a provided range
  - forward-fills gaps as a simple alignment placeholder
  - preserves symbol identity

- `merge_hourly_frames()`
  - joins aligned hourly frames for downstream modeling

- `dataframe_to_hourly_fact_rows()`
  - converts DataFrame rows into tuples matching `abm_hourly_facts` insertion order

Why forward fill is only emphasized for tradfi:

TradFi has non-continuous trading sessions.
Crypto and many exogenous features should generally preserve missingness unless a specific domain rule says otherwise.

### Scheduler wiring
Module:

- `scheduler.py`

What it does:

- builds an APScheduler `BackgroundScheduler`
- registers one hourly ETL job at minute `05` UTC

Current scheduler safety settings:

- `max_instances=1`
- `coalesce=True`
- `replace_existing=True`
- `misfire_grace_time=900`

Why these matter:

- prevents overlapping ETL runs
- avoids replaying many missed jobs after downtime
- keeps job registration deterministic

--------------------------------------------------
## Configuration

Defined in:

- `src/astro_abm/config.py`

### Environment variables

Market data:

- `POLYGON_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `LUNARCRUSH_API_KEY`

QuestDB:

- `QUESTDB_HOST`
- `QUESTDB_PG_PORT`
- `QUESTDB_USER`
- `QUESTDB_PASSWORD`
- `QUESTDB_DATABASE`

Provider selection:

- `TRADFI_PROVIDER`

Notes:

- The repo does not yet include `.env.example`
- live provider credentials are still an open blocker in `.planning/STATE.md`
- QuestDB defaults in `config.py` are for disposable local development only and should be overridden outside a local test setup

--------------------------------------------------
## Installation

Python requirement:

- Python 3.11+

Main dependencies:

- `python-binance`
- `requests`
- `psycopg[binary]`
- `pyswisseph`
- `pandas`
- `apscheduler`

Install in editable mode:

```bash
pip install -e .[dev]
```

If you are using `uv`:

```bash
uv pip install -e .[dev]
```

--------------------------------------------------
## Running Tests

Run everything:

```bash
pytest -q
```

Run by feature area:

```bash
pytest tests/test_market_data.py -q
pytest tests/test_space_weather.py -q
pytest tests/test_ephemeris.py -q
pytest tests/test_social_sentiment.py -q
pytest tests/test_etl.py -q
```

--------------------------------------------------
## What is tested today

The tests are designed around behavior, not just imports. They are currently unit tests, not full live-provider or end-to-end integration tests.

Covered areas include:

- Binance kline normalization
- Polygon bar normalization
- Alpha Vantage timezone normalization
- QuestDB batch writer shaping
- NOAA table-feed parsing
- X-ray channel filtering
- Kp hourly expansion
- moon phase percentage and angular features
- LunarCrush hourly payload normalization
- ETL alignment, merge, row shaping, and scheduler wiring

--------------------------------------------------
## Known Gaps / Next Logical Work

This repo is now a strong foundation, but it is not yet a one-command live pipeline.

The most natural next steps are:

### 1. End-to-end ETL entrypoint
Add something like:

- `scripts/run_hourly_etl.py`

This should:

- fetch market data
- fetch NOAA data
- compute ephemeris features
- fetch social sentiment
- align everything with pandas
- write bars + facts into QuestDB

### 2. Credential/bootstrap ergonomics
Add:

- `.env.example`
- startup docs for provider credentials
- optional config validation command

### 3. Unified writer for `abm_hourly_facts`
The repo currently shapes rows for the facts table, but it does not yet include a finished dedicated writer class equivalent to `QuestDBMarketBarWriter` for all fact-row inserts.

### 4. Simulation layer
After the live hourly pipeline is stable, the project can move into:

- retail swarm agents
- CEO agents
- replay / scenario windows
- validation experiments against sentiment perturbation hypotheses

--------------------------------------------------
## Summary

If you want to understand the repo quickly, read it in this order:

1. `README.md`
2. `.planning/ROADMAP.md`
3. `sql/schema_phase1.sql`
4. `src/astro_abm/models.py`
5. `src/astro_abm/market_data/`
6. `src/astro_abm/features/`
7. `src/astro_abm/etl/`
8. `tests/`

The important mental model is simple:

- source modules fetch or compute hourly signals
- feature/bar models normalize them
- ETL helpers align them to one UTC timeline
- QuestDB stores them for later ABM and research work

This repository is the tested hourly data-and-feature scaffold for the future Astro ABM system.

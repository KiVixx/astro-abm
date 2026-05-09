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
- ETL alignment and scheduling helpers

The entire MVP is standardized around a single rule:

All features must align to UTC 1-hour buckets.

--------------------------------------------------
## Current Status

Implemented and unit-tested:

- Phase 1 — QuestDB setup and schema
- Phase 2 — crypto + tradfi market-data provider and normalization skeleton
- Phase 3 — NOAA SWPC parsing helpers + local ephemeris feature layer
- Phase 4 — price-action and derivatives feature ingestion
- Phase 5 — ETL alignment helpers, hourly/daily maintenance, Docker runtime
- Active-only data completeness reporting

Current test status:

```bash
uv run pytest -q
```

Not yet implemented:

- ABM simulation runtime and agent logic
- provider credential validation / bootstrap command
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
- crypto positioning, funding, and price-action features

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
├── .env.example
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
│       ├── live.py
│       ├── pipeline.py
│       └── scheduler.py
├── tests/
│   ├── test_market_data.py
│   ├── test_space_weather.py
│   ├── test_ephemeris.py
│   ├── test_social_sentiment.py
│   ├── test_etl.py
│   └── test_live_etl.py
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

Start QuestDB plus the Docker maintenance daemon:

```bash
docker compose -f docker-compose.questdb.yml --profile maintenance up -d --build
```

The maintenance service runs:

- hourly maintenance at minute `05` each hour
- daily archive maintenance at `00:20` UTC
- one hourly refresh on container start by default

It intentionally excludes disabled sentiment/vendor providers from scheduled maintenance.

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
- `src/astro_abm/market_data/binance_historical.py`
- `src/astro_abm/market_data/binance_derivatives.py`
- `src/astro_abm/market_data/tradfi.py`
- `src/astro_abm/features/price_action.py`
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

### Historical spot OHLCV backfill

Command:

```bash
astro-abm-backfill-binance-spot \
  --symbols BTCUSDT,ETHUSDT \
  --start 2017-01-01T00:00:00Z
```

What it does:

- pages Binance spot 1-hour klines from the official `/api/v3/klines` endpoint
- writes rows to `market_ohlcv_1h`
- skips timestamps already present for the same symbol/source

### Price-action feature layer

Command:

```bash
astro-abm-build-price-features \
  --symbols BTCUSDT,ETHUSDT \
  --start 2017-01-01T00:00:00Z
```

Current metrics:

- `price_return_1h`
- `price_log_return_1h`
- `price_range_pct`
- `price_drawdown_24h`
- `price_realized_vol_24h`
- `price_downside_vol_24h`
- `price_volume_zscore_24h`
- `price_shock_score`

### Binance futures positioning layer

Command:

```bash
astro-abm-backfill-binance-derivatives \
  --symbols BTCUSDT,ETHUSDT \
  --start 2019-09-01T00:00:00Z
```

Current metrics:

- `funding_rate`
- `funding_rate_annualized`
- `funding_mark_price`
- `open_interest`
- `open_interest_value`

Funding-rate history can go much further back than open-interest history. Binance's official open-interest statistics endpoint only exposes the latest 1 month, so the derivatives backfill treats funding as the long-history positioning baseline and OI as a recent-context feature.

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

### QuestDB hourly fact writer
Module:

- `src/astro_abm/storage/questdb.py`

What it does:

- `QuestDBHourlyFactWriter`
- accepts shaped fact dictionaries or row tuples
- writes unified feature rows into `abm_hourly_facts`

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
## Phase 4 — Price Action and Positioning Layer

The active research path currently favors hard market data over narrative sentiment:

- Binance spot OHLCV
- price-action features derived from closed 1H candles
- Binance futures funding and open interest
- Binance Vision historical metrics

ASKGROK, LunarCrush, Coinalyze, and Tardis integrations are disabled from the main CLI, Docker maintenance flow, and default completeness report. Their old provider modules are left in the tree only as recoverable experimental code.

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

### Live ETL entrypoint
Module:

- `live.py`

What it does:

- wires crypto market bars, optional tradfi bars, NOAA space weather, and ephemeris rows
- writes OHLCV rows through `QuestDBMarketBarWriter`
- writes feature rows through `QuestDBHourlyFactWriter`
- exposes a console command:

```bash
astro-abm-live
```

The live entrypoint is unit-tested with fake providers. A conservative local smoke run has been validated for QuestDB, ephemeris, NOAA facts, Binance, and Polygon.

Backfill safety defaults:

- hourly windows only
- provider errors are recorded without stopping the entire batch
- one summary row is written to `etl_runs`

--------------------------------------------------
## Configuration

Defined in:

- `src/astro_abm/config.py`

### Environment variables

Market data:

- `POLYGON_API_KEY`
- `ALPHA_VANTAGE_API_KEY`

QuestDB:

- `QUESTDB_HOST`
- `QUESTDB_PG_PORT`
- `QUESTDB_USER`
- `QUESTDB_PASSWORD`
- `QUESTDB_DATABASE`

Provider selection:

- `TRADFI_PROVIDER`

Notes:

- The repo includes `.env.example`
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
- `python-dotenv`

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
pytest tests/test_live_etl.py -q
pytest tests/test_backfill_askgrok.py -q
pytest tests/test_feature_summary.py -q
pytest tests/test_price_action.py -q
pytest tests/test_binance_historical.py -q
pytest tests/test_binance_derivatives.py -q
```

--------------------------------------------------
## What is tested today

The tests are designed around behavior, not just imports. They are currently unit tests, not full live-provider or end-to-end integration tests.

Covered areas include:

- Binance kline normalization
- Binance historical spot kline backfill normalization
- Binance futures funding/open-interest feature shaping
- price-action feature generation
- Polygon bar normalization
- Alpha Vantage timezone normalization
- QuestDB batch writer shaping
- unified QuestDB fact writer shaping
- NOAA table-feed parsing
- X-ray channel filtering
- Kp hourly expansion
- moon phase percentage and angular features
- ETL run-log writer shaping
- ETL alignment, merge, row shaping, and scheduler wiring
- live ETL provider orchestration with fake providers

--------------------------------------------------
## Known Gaps / Next Logical Work

This repo is now a strong foundation, with a tested one-command live ETL skeleton. The next gap is building enough historical price and derivatives coverage to compare price-only features against positioning features.

The most natural next steps are:

### 1. Validate QuestDB locally
Start QuestDB:

```bash
docker compose -f docker-compose.questdb.yml up -d
```

Then apply:

```bash
psql -h localhost -p 8812 -U admin -d qdb -f sql/schema_phase1.sql
```

The schema file is idempotent and only creates tables; it does not seed sample facts.

### 2. Backfill hard market data

Start with price and futures positioning before expanding narrative sentiment:

```bash
astro-abm-backfill-binance-spot --symbols BTCUSDT,ETHUSDT --start 2017-01-01T00:00:00Z
astro-abm-build-price-features --symbols BTCUSDT,ETHUSDT --start 2017-01-01T00:00:00Z
astro-abm-backfill-binance-derivatives --symbols BTCUSDT,ETHUSDT --start 2019-09-01T00:00:00Z
```

### 3. Configure provider credentials
Copy `.env.example` to `.env`, then fill whichever providers you plan to test first. The package loads `.env` automatically when configuration is read.

- `POLYGON_API_KEY` or `ALPHA_VANTAGE_API_KEY`

### 4. Run the live ETL command
After installing the package in editable mode:

```bash
astro-abm-live
```

### 5. Add a config validation command
The live command currently skips optional providers when credentials are missing. A dedicated validation command should make missing credentials and database availability explicit before a live run starts.

### 6. Explore feature-store data

Print a compact QuestDB summary:

```bash
astro-abm-feature-summary
```

Use that output to decide which time windows deserve deeper analysis before writing ABM simulation logic.

### 7. Simulation layer
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

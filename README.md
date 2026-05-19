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

Chinese maintainer briefing:

- [Astro ABM 項目維護者簡報](docs/research/project_maintenance_brief_zh.md)
- [一鍵運行與資料維護指南](docs/OPEN_SOURCE_OPERATIONS.zh.md)

One-command local operations:

```bash
make bootstrap
make status
make smoke
```

`make bootstrap` creates a local `.env` from `.env.example` when needed, starts
QuestDB plus the maintenance daemon, applies the hourly and daily research
schemas, ensures the 1926-2025 core daily astro dataset is built and ingested,
and prints database/data readiness. Generated outputs remain under
`astro_research/output/`, and real local research CSVs remain under
`astro_research/data/local/`; both are intentionally git-ignored.

For manual maintenance, `make maintain-now` tolerates partial transient upstream
failures while preserving the failed-task summary. Use
`uv run python scripts/astro_abm_ops.py maintain-now` directly when you need a
strict non-zero exit code.

`make astro-daily` can be run directly to ensure the deterministic 100-year
daily astro data exists without running the hourly/daily market maintenance.

Current test status:

```bash
make test
# or: uv run --extra dev pytest -q
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

On macOS with OrbStack, install the user LaunchAgent if you want the stack to
come back automatically after login/reboot:

```bash
ops/launchd/install_astro_abm_launchd.sh
```

The LaunchAgent runs at login and then every 5 minutes. It opens OrbStack if the
Docker API is unavailable, then idempotently runs:

```bash
docker compose -f docker-compose.questdb.yml --profile maintenance up -d
```

The installed LaunchAgent stores its runtime wrapper in
`~/Library/Application Support/AstroABM/` so macOS background permissions do not
need to read scripts from `~/Documents`. Logs are written to
`~/Library/Logs/AstroABM/`. To remove the LaunchAgent:

```bash
ops/launchd/uninstall_astro_abm_launchd.sh
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

### 7. Research astro volatility windows

Run a rolling-regime alpha scan that uses future-computable ephemeris features
to score whether specific astro states historically coincided with unusually
large next-24h volatility:

```bash
astro-abm-astro-volatility-alpha \
  --event-mode rolling_quantile \
  --event-window-hours 8760 \
  --event-min-periods 2160 \
  --output outputs/astro_volatility_alpha_rolling.csv
```

Turn the strongest held-out signal rows into a future risk calendar:

```bash
astro-abm-astro-risk-calendar \
  --signals outputs/astro_volatility_alpha_rolling.csv \
  --cluster-mode station_direction \
  --frequency daily \
  --output outputs/astro_risk_calendar_daily.csv
```

The calendar is a research product, not a trade signal. Correlated ephemeris
features can cluster around the same station/retrograde event, so the default
calendar collapses raw feature rows into event clusters such as Venus
direct-to-retrograde station or Mercury retrograde-to-direct station. High
scores should be read as an event-window warning rather than independent
evidence.

### 8. Build a 100-year daily astro research dataset

The hourly crypto pipeline remains the trading-data layer. Long-horizon
retrograde, station, lunar, aspect, and macro-history research lives in the
separate `astro_research/` daily layer.

The daily layer uses its own QuestDB tables:

- `astro_daily_positions`
- `astro_daily_facts`
- `astro_retrograde_cycles`
- `astro_event_windows`
- `astro_daily_features`

The first dataset is configured by `astro_research/configs/astro_daily.yaml`.
It samples deterministic Swiss Ephemeris positions at `00:00 UTC`, scans
retrograde station sign flips on a buffered range, refines exact station
timestamps, pairs station-in/out events into retrograde cycles, and labels each
daily row with:

- `direct`
- `pre_station`
- `retrograde_entry`
- `retrograde_core`
- `retrograde_exit`
- `post_station`

Build a smoke dataset:

```bash
python scripts/build_astro_daily.py \
  --config astro_research/configs/astro_daily.yaml \
  --start 2020-01-01 \
  --end 2021-12-31 \
  --write-parquet astro_research/output/parquet/astro_daily_smoke_2020_2021 \
  --dry-run
```

Build the full 100 calendar-year dataset:

```bash
python scripts/build_astro_daily.py \
  --config astro_research/configs/astro_daily.yaml \
  --start 1926-01-01 \
  --end 2025-12-31 \
  --write-parquet astro_research/output/parquet/astro_daily_1926_2025 \
  --no-parquet \
  --dry-run
```

MVP3 also writes:

- `astro_moon_phase_events`
- `astro_aspect_events`
- Parquet files next to each CSV snapshot

All-body exact aspect scans are the expensive part of the daily layer. The
default config scans Sun through Pluto, including Moon pairs, so full 100-year
rebuilds should be treated as long batch jobs. For frequent iteration, use a
small date range first and keep generated snapshots under
`astro_research/output/`, which is git-ignored.

Repository hygiene tests enforce this boundary: generated
`astro_research/output/` files, real local research CSVs under
`astro_research/data/local/`, `.env`, and private key files must not be tracked
by git. Commit only the local data README, example schemas, and
`LOCAL_DATA_PROVENANCE.json` manifest.

For maintainable 100-year exact aspect builds, use the optimized chunk mode.
It writes one pair/year snapshot per directory:

```bash
python scripts/build_astro_daily.py \
  --config astro_research/configs/astro_daily.yaml \
  --aspect-profile macro_core \
  --aspect-start 1926-01-01 \
  --aspect-end 2025-12-31 \
  --write-parquet astro_research/output/parquet/aspect_chunks/macro_core_1926_2025 \
  --workers 4 \
  --resume \
  --skip-existing
```

Supported aspect profiles:

- `macro_core`: Mars/Jupiter/Saturn/Uranus/Neptune/Pluto
- `market_core`: Mercury/Venus/Mars/Jupiter/Saturn
- `lunar_short_term`: Moon with Sun/Mercury/Venus/Mars/Saturn/Uranus
- `all_no_moon`: Sun through Pluto excluding Moon pairs
- `all`: Sun through Pluto including Moon pairs

Validate aspect chunks:

```bash
python scripts/validate_astro_daily.py \
  --config astro_research/configs/astro_daily.yaml \
  --start 1926-01-01 \
  --end 2025-12-31 \
  --aspect-only \
  --aspect-chunks-dir astro_research/output/parquet/aspect_chunks/macro_core_1926_2025 \
  --aspect-profile macro_core \
  --output astro_research/output/reports/aspect_chunks_macro_core_1926_2025_validation.md
```

Benchmark profile cost before running a large build:

```bash
python scripts/benchmark_aspect_build.py \
  --profiles macro_core,market_core,lunar_short_term \
  --year 2020 \
  --workers 2
```

Validate a snapshot:

```bash
python scripts/validate_astro_daily.py \
  --config astro_research/configs/astro_daily.yaml \
  --snapshot-dir astro_research/output/parquet/astro_daily_1926_2025 \
  --start 1926-01-01 \
  --end 2025-12-31 \
  --output astro_research/output/reports/astro_daily_validation_1926_2025.md
```

Ingest is intentionally a separate step and supports dry-run first:

```bash
python scripts/ingest_astro_daily.py \
  --parquet-dir astro_research/output/parquet/astro_daily_1926_2025 \
  --dry-run
```

Swiss Ephemeris licensing matters for public or commercial distribution; see
`LICENSE_NOTES.md` before turning this into a hosted service.

### 9. Daily market layer and event study v1

MVP4 adds a daily market research layer and a first event-study engine. The
market config lives at `astro_research/configs/market_assets.yaml` and covers:

- `BTC`
- `ETH`
- `SPX`
- `NDX`
- `Gold`
- `DXY`
- `VIX`
- `US10Y`

Providers are intentionally pluggable:

- `local_csv` for reproducible local research snapshots
- `fred` for daily macro/rates series when `FRED_API_KEY` is available
- `yfinance` as an optional provider that is skipped gracefully when the
  package is not installed

Build daily bars and features:

```bash
python scripts/build_market_daily.py \
  --config astro_research/configs/market_assets.yaml \
  --asset BTC \
  --source local_csv \
  --start 2020-01-01 \
  --end 2020-12-31 \
  --write-parquet astro_research/output/parquet/market_daily \
  --dry-run
```

The output tables are:

- `market_daily_bars`
- `market_daily_features`

`market_daily_features` includes 1d log returns, 3/5/10/20d returns, realized
volatility, trailing drawdown, 252d absolute-return percentile ranks, and
extreme-move flags.

Run the first event study:

```bash
python scripts/run_event_study.py \
  --config astro_research/configs/event_study_v1.yaml \
  --output astro_research/output/reports/event_study_v1
```

The v1 study is calendar-day based. It compares station windows, station
clusters, and macro-core aspect windows against all non-event days,
month-matched baselines, and weekday-matched baselines. It outputs bootstrap
confidence intervals, permutation p-values, Benjamini-Hochberg FDR q-values,
and placebo percentiles.

### 10. Formal research layer MVP5

MVP5 turns the daily astro dataset into a reproducible historical association
research layer. The research question is deliberately limited:

> Do specific astro event windows historically coincide with higher financial
> stress or market turmoil?

The layer does not make causal claims. Formal reports should use language such
as association, historical relationship, stress-regime exploration, or event
study.

New configs:

- `astro_research/configs/data_sources.yaml`
- `astro_research/configs/market_assets_real.yaml`
- `astro_research/configs/macro_series.yaml`
- `astro_research/configs/financial_stress.yaml`
- `astro_research/configs/research_events.yaml`
- `astro_research/configs/research_hypotheses.yaml`
- `astro_research/configs/research_batch_v1.yaml`
- `astro_research/configs/crisis_casebook.yaml`

New canonical research tables:

- `data_source_registry`
- `macro_daily_observations`
- `market_asset_coverage`
- `financial_stress_daily`
- `research_events`
- `research_hypotheses`
- `event_study_runs`
- `event_study_results_v2`
- `world_event_catalog`

Build the source registry:

```bash
python scripts/build_data_source_registry.py \
  --config astro_research/configs/data_sources.yaml \
  --output astro_research/output/reports/source_registry.md
```

The registry preserves local provenance metadata such as coverage dates,
local-only flags, redistribution/publication status, proxy markers, and
licensing-review caveats. These fields are part of the `data_source_registry`
table schema and should survive optional QuestDB ingest.

Build real macro data when `FRED_API_KEY` is available:

```bash
python scripts/build_macro_daily.py \
  --config astro_research/configs/macro_series.yaml \
  --start 1926-01-01 \
  --end 2025-12-31 \
  --write-parquet astro_research/output/parquet/macro_daily
```

Without `FRED_API_KEY`, the macro build exits successfully with a warning and
an empty snapshot, so local/synthetic smoke tests remain runnable.

Build financial stress features:

```bash
python scripts/build_financial_stress_daily.py \
  --config astro_research/configs/financial_stress.yaml \
  --write-parquet astro_research/output/parquet/financial_stress
```

The stress layer is coverage-aware. Missing components remain null; cross-asset
stress is calculated from available components and marked
`insufficient_coverage` when too little data is present.

Normalize research events:

```bash
python scripts/build_research_events.py \
  --config astro_research/configs/research_events.yaml \
  --write-parquet astro_research/output/parquet/research_events
```

Register formal hypotheses:

```bash
python scripts/register_hypotheses.py \
  --config astro_research/configs/research_hypotheses.yaml \
  --git-commit auto \
  --write-parquet astro_research/output/parquet/research_hypotheses
```

Run the first formal batch:

```bash
python scripts/run_research_batch.py \
  --config astro_research/configs/research_batch_v1.yaml \
  --run-id research_batch_v1_1926_2025 \
  --output astro_research/output/reports/research_batch_v1_1926_2025
```

Batch report directories include `config_snapshot.yaml`,
`hypothesis_snapshot.yaml`, `coverage_report.csv`, `event_traceability.csv`,
`warnings.json`, `run_manifest.json`, `summary.md`, and `top_findings.md`.
`run_manifest.json` is the machine-readable reproducibility anchor: it records
the run id, config snapshot hash, git commit/dirty state, readiness status,
input row/schema fingerprints, output artifact hashes, and warning payload. The
traceability file is part of the same contract: aspect-family studies such as
H003 and H004 must show `astro_aspect_events` as their source table with
non-zero eligible event counts and source event id examples.

Build the descriptive crisis casebook:

```bash
python scripts/build_crisis_casebook.py \
  --config astro_research/configs/crisis_casebook.yaml \
  --output astro_research/output/reports/casebook
```

Casebook reports are generated artifacts and should stay under
`astro_research/output/`. Each case report is descriptive only: it lists input
availability, market feature window summaries, financial-stress summaries,
astro event family/source-table counts, and missing components. These reports
are for review of historical overlap and must not be interpreted as causal
claims, forecasts, investment advice, or trading signals.

Run the end-to-end research workflow checkpoint:

```bash
uv run python scripts/research_workflow_checkpoint.py
```

The checkpoint regenerates the current research-output path in order: crisis
casebook reports and `index.md`, the H001-H004 exploratory formal batch, and
the research readout summary. It writes generated artifacts under
`astro_research/output/reports/research_workflow_checkpoint/`, checks that no
generated outputs or local CSVs are staged, scans the staged diff for common
secret patterns, and verifies that the readout remains descriptive only: no
causality, prediction, investment advice, or trading signal.

Validate the research layer:

```bash
python scripts/validate_research_layer.py \
  --output astro_research/output/reports/research_layer_validation.md
```

Validation checks duplicate keys, missing tables, source-registry metadata
presence, macro original/transformed frequency consistency, coverage audit
columns, event-study result hypothesis ids, research run manifest completeness,
and H003/H004 aspect traceability when `event_traceability.csv` is available.
It also warns when timing-sensitive daily research tables lack `available_ts`
or `observed_ts`; those warnings mean the current output should be interpreted
as historical association/event-study context, not as a point-in-time backtest.

### 11. Simulation layer
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

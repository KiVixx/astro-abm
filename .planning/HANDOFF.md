# Astro ABM Handoff

Last updated: 2026-05-07

This file is a compact handoff note for resuming the project from a fresh Codex session or a different account.

## Repository

- GitHub: `git@github.com:KiVixx/astro-abm.git`
- Local path: `/Users/Apple/Documents/New project/astro-abm`
- Main branch latest pushed commit at handoff:
  - `c1e1db3 feat: add Binance Vision metrics backfill`
- Validation at handoff:
  - `uv run pytest -q`
  - `69 passed in 1.92s`

## Project Purpose

Astro ABM is currently a data-engineering foundation for a future agent-based market simulator.

The working hypothesis is that market behavior can be studied by aligning several hourly feature families on one UTC timeline:

- crypto market price and volume
- derivatives positioning such as open interest and funding-related metrics
- social sentiment adapters
- astronomy ephemeris features
- space-weather features such as solar wind, IMF Bz, X-ray flux, and Kp

The ABM simulation engine is not built yet. The current project focus is building a reliable feature store first.

## Architecture Snapshot

Primary storage is QuestDB.

Important tables/views:

- `abm_hourly_facts`
  - Flexible fact table for hourly features and derivative metrics.
- `market_ohlcv_1h`
  - Dedicated OHLCV table.
- `v_space_weather_unified`
  - Unifies authoritative NASA OMNI and provisional NOAA SWPC recent data.
- `v_open_interest_unified`
  - Unifies OI sources by source priority.

Core rule:

- All main analysis features currently align to UTC 1-hour buckets.

## Implemented Data Sources

Market and price:

- Binance spot OHLCV backfill
- Binance derivatives backfill
- price-action feature builder

Derivatives and positioning:

- Binance futures open interest current collector
- Binance futures recent historical OI
- Coinalyze OI provider
- Coinalyze split interval handling:
  - `coinalyze_1h`
  - `coinalyze_daily`
- Binance Vision futures metrics backfill
  - official Binance data
  - cached ZIP source files
  - current ETL aggregates the 5m raw metrics into 1h facts

Astronomy and space weather:

- local ephemeris via `pyswisseph`
- NASA OMNI historical space weather
- NOAA GOES X-ray
- NOAA SWPC recent overlay

Sentiment:

- LunarCrush parser remains in the repo, but not preferred as the main path.
- ASKGROK adapter support exists in the main repo.
- Separate ASKGROK service project lives outside this repo at:
  - `/Users/Apple/Documents/New project 2`

## Current Local Data State

Approximate QuestDB size at handoff:

- Docker volume `astro-abm_questdb-data`: about `490.2MB`
- `/var/lib/questdb`: about `474MB`

Binance Vision ZIP cache:

- Path: `/Users/Apple/.cache/astro-abm/binance-vision`
- Size: about `46MB`
- ZIP count: `3674`
- Contains cached official Binance futures metrics ZIP files for BTCUSDT and ETHUSDT.
- The raw CSVs are 5-minute snapshots, so they can later be reused to rebuild 30m, 15m, or 5m feature layers without redownloading.

Important local-only state not stored in GitHub:

- `.env`
- QuestDB Docker volume
- Binance Vision cache
- any running Docker container state
- ASKGROK browser login/session state in the separate ASKGROK project

## OI Data Coverage Snapshot

Important raw OI sources currently in QuestDB:

- `binance_vision_metrics`
  - BTCUSDT: starts `2020-09-01`, latest checked around `2026-04-28`
  - ETHUSDT: starts `2021-12-01`, latest checked around `2026-04-28`
  - metrics include:
    - `open_interest`
    - `open_interest_value`
    - `count_toptrader_long_short_ratio`
    - `sum_toptrader_long_short_ratio`
    - `count_long_short_ratio`
    - `sum_taker_long_short_vol_ratio`
- `coinalyze_1h`
  - recent 1h OI data
- `coinalyze_daily`
  - longer daily fallback data
- `binance_futures` / `binance_futures_current`
  - recent official Binance OI collector data
- `tardis_binance_futures`
  - sample only, not a full production source

`v_open_interest_unified` intentionally prioritizes official Binance data above vendor fallback data where timestamps overlap.

## Useful Commands

Start QuestDB:

```bash
docker compose -f docker-compose.questdb.yml up -d
```

Start QuestDB plus the Docker maintenance daemon:

```bash
docker compose -f docker-compose.questdb.yml --profile maintenance up -d --build
```

Stop QuestDB:

```bash
docker compose -f docker-compose.questdb.yml down
```

Run tests:

```bash
uv run pytest -q
```

Check data completeness:

```bash
uv run astro-abm-data-completeness
```

Run 1H maintenance without social sentiment:

```bash
uv run astro-abm-maintain-hourly
```

Run the scheduler daemon directly:

```bash
uv run astro-abm-maintenance-daemon --run-on-start hourly
```

Run daily archive/data-health maintenance:

```bash
uv run astro-abm-maintain-daily
```

Feature summary:

```bash
uv run astro-abm-feature-summary
```

Backfill Binance Vision metrics:

```bash
uv run astro-abm-backfill-binance-vision-metrics
```

Run ASKGROK service separately:

```bash
cd "/Users/Apple/Documents/New project 2"
npm start
```

ASKGROK main sentiment endpoint:

```bash
curl -X POST http://localhost:3000/sentiment/crypto \
  -H 'Content-Type: application/json' \
  -d '{
    "startUtc": "2022-05-20T00:00:00Z",
    "endUtc": "2022-05-20T01:00:00Z",
    "assets": ["BTC", "ETH", "LUNA", "UST"],
    "timeoutMs": 180000
  }'
```

## Current Strategic Direction

The project went through a loop about whether non-price data is worth using.

Current conclusion:

- Price is the most complete consensus signal.
- Non-price data should not be treated as magic directional alpha.
- Non-price data is more useful as:
  - market regime filter
  - leverage / fragility proxy
  - confirmation or contradiction signal
  - feature context for interpreting price moves

Most promising next feature families:

- price spreads and relative strength
- spot/perp basis and OI context
- funding/open-interest regime filters
- volatility and liquidity state
- price-action features combined with derivatives state

## Recommended Next Steps

1. Stabilize 1H continuous data maintenance.
   - Keep 1H as the canonical model layer.
   - Use `astro-abm-maintain-hourly` for recent market/OI/space-weather/ephemeris refreshes.
   - Use `astro-abm-maintain-daily` for archive overlays and slow authoritative sources.
   - Run `astro-abm-data-completeness` after maintenance and check `health=OK/STALE/MISSING`.

2. Build derivatives regime features.
   - OI change rate
   - OI value change rate
   - price up + OI up / price down + OI up regime labels
   - trader ratio extremes
   - taker long/short pressure

3. Build relative price features.
   - BTC vs ETH strength
   - spot/perp spread if available
   - volatility compression/expansion
   - trend vs chop labels

4. Run a small feature-quality report.
   - Start with BTC and ETH only.
   - Avoid expanding symbols until the feature methodology is stable.

5. Only after that, start simple backtests or model experiments.
   - Do not jump directly to ABM before feature usefulness is checked.

## Notes For Future Codex Session

Start by reading:

- `.planning/HANDOFF.md`
- `.planning/STATE.md`
- `README.md`
- `sql/schema_phase1.sql`
- `pyproject.toml`

Then run:

```bash
git status --short --branch
uv run pytest -q
docker compose -f docker-compose.questdb.yml ps
```

Do not overwrite or delete local QuestDB data, `.env`, or cache directories unless explicitly requested.

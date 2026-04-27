# STATE

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Create a reproducible hourly feature pipeline that lets the system test whether exogenous astro/space-weather signals can explain or perturb simulated market sentiment and agent behavior.
**Current focus:** Phase 7 — Price and Positioning Baselines

## Current Status

- Milestone: MVP hourly data foundation
- Active phase: 7
- Latest artifact: Binance historical spot backfill, price-action feature layer, Binance futures funding/OI layer, ASKGROK backfill runner, and ETL run logs
- Verification status: unit tests passing; QuestDB running; conservative live ephemeris/NOAA/Binance/Polygon run succeeded

## Open Blockers

- ASKGROK is a local dependency and must be running for `SOCIAL_SENTIMENT_PROVIDER=askgrok` or `astro-abm-backfill-askgrok`.
- ASKGROK retrospective web-research sentiment is not equivalent to raw historical X firehose data.
- LunarCrush remains optional but is no longer the recommended primary social provider.
- Binance open-interest statistics only expose the latest 1 month; funding-rate history is the longer-horizon derivatives baseline.

## Recent Decisions

- Use QuestDB as the primary time-series database.
- Use UTC hour-bucket `ts` as the designated timestamp across aligned tables.
- Preserve `observed_ts` and `available_ts` for provenance and leakage control.
- Maintain both a unified aligned facts table and a dedicated hourly OHLCV table.
- Add a tested live ETL skeleton before attempting provider-specific production hardening.
- Use ASKGROK as the primary social-sentiment adapter and keep LunarCrush as optional fallback.
- Treat price as the consensus baseline and derivatives positioning as a regime/fragility layer before expanding narrative features.

## Next Step

Build historical hard-data baselines:
1. backfill Binance spot OHLCV as far back as available for priority symbols
2. build price-action feature rows from OHLCV
3. backfill Binance futures funding rates as far back as available
4. backfill open interest for the latest 1 month where Binance exposes it
5. compare price-only features against derivatives positioning and ASKGROK narrative rows

## Resume Anchor

If resuming later, start with:
- .planning/ROADMAP.md
- .env.example
- src/astro_abm/etl/live.py
- src/astro_abm/storage/questdb.py

# STATE

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Create a reproducible hourly feature pipeline that lets the system test whether exogenous astro/space-weather signals can explain or perturb simulated market sentiment and agent behavior.
**Current focus:** Phase 6 — Live ETL Validation & Bootstrap

## Current Status

- Milestone: MVP hourly data foundation
- Active phase: 6
- Latest artifact: ASKGROK social sentiment adapter, live ETL skeleton, `.env.example`, and unified hourly fact writer
- Verification status: unit tests passing; QuestDB running; conservative live ephemeris/NOAA/Binance/Polygon run succeeded

## Open Blockers

- ASKGROK is a local dependency and must be running for `SOCIAL_SENTIMENT_PROVIDER=askgrok`.
- ASKGROK retrospective web-research sentiment is not equivalent to raw historical X firehose data.
- LunarCrush remains optional but is no longer the recommended primary social provider.

## Recent Decisions

- Use QuestDB as the primary time-series database.
- Use UTC hour-bucket `ts` as the designated timestamp across aligned tables.
- Preserve `observed_ts` and `available_ts` for provenance and leakage control.
- Maintain both a unified aligned facts table and a dedicated hourly OHLCV table.
- Add a tested live ETL skeleton before attempting provider-specific production hardening.
- Use ASKGROK as the primary social-sentiment adapter and keep LunarCrush as optional fallback.

## Next Step

Validate the live runtime path:
1. start ASKGROK from `/Users/Apple/Documents/New project 2`
2. set `SOCIAL_SENTIMENT_PROVIDER=askgrok`
3. run `astro-abm-live` with crypto/tradfi/social symbols enabled
4. confirm ASKGROK rows land in `abm_hourly_facts`
5. decide whether to add controlled historical loopback/backfill windows

## Resume Anchor

If resuming later, start with:
- .planning/ROADMAP.md
- .env.example
- src/astro_abm/etl/live.py
- src/astro_abm/storage/questdb.py

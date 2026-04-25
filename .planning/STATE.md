# STATE

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Create a reproducible hourly feature pipeline that lets the system test whether exogenous astro/space-weather signals can explain or perturb simulated market sentiment and agent behavior.
**Current focus:** Phase 6 — Live ETL Validation & Bootstrap

## Current Status

- Milestone: MVP hourly data foundation
- Active phase: 6
- Latest artifact: live ETL skeleton, `.env.example`, and unified hourly fact writer
- Verification status: unit tests passing; QuestDB running; conservative live ephemeris/NOAA fact run succeeded

## Open Blockers

- No provider credentials configured yet for Polygon/Alpha Vantage/LunarCrush.
- Live crypto market-bar write has not yet been smoke-tested against Binance from this environment.
- Live tradfi and LunarCrush ingestion require provider credentials.

## Recent Decisions

- Use QuestDB as the primary time-series database.
- Use UTC hour-bucket `ts` as the designated timestamp across aligned tables.
- Preserve `observed_ts` and `available_ts` for provenance and leakage control.
- Maintain both a unified aligned facts table and a dedicated hourly OHLCV table.
- Add a tested live ETL skeleton before attempting provider-specific production hardening.

## Next Step

Validate the live runtime path:
1. add provider keys to `.env`
2. run `astro-abm-live` with crypto/tradfi/social symbols enabled
3. confirm `market_ohlcv_1h` receives market bars
4. add config validation and live integration tests around the real runtime assumptions

## Resume Anchor

If resuming later, start with:
- .planning/ROADMAP.md
- .env.example
- src/astro_abm/etl/live.py
- src/astro_abm/storage/questdb.py

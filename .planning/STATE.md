# STATE

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Create a reproducible hourly feature pipeline that lets the system test whether exogenous astro/space-weather signals can explain or perturb simulated market sentiment and agent behavior.
**Current focus:** DataOps — 1H continuous acquisition and maintenance

## Current Status

- Milestone: MVP hourly data foundation
- Active phase: 1H feature-store maintenance
- Latest artifact: hourly/daily maintenance entrypoints, Docker maintenance daemon, Binance Vision metrics backfill, Coinalyze interval split, data completeness freshness flags, and handoff note
- Verification status: unit tests passing; QuestDB running; current focus is keeping data fresh before expanding models or intervals

## Open Blockers

- ASKGROK is a local dependency and must be running for `SOCIAL_SENTIMENT_PROVIDER=askgrok` or `astro-abm-backfill-askgrok`.
- ASKGROK retrospective web-research sentiment is not equivalent to raw historical X firehose data.
- ASKGROK sentiment is intentionally ignored in the current maintenance push.
- LunarCrush remains optional but is no longer the recommended primary social provider.
- Binance API open-interest statistics only expose the latest 1 month, but Binance Vision metrics now provide official longer historical OI coverage for priority symbols.
- Local-only assets such as `.env`, QuestDB volume, and Binance Vision ZIP cache are not stored in Git.

## Recent Decisions

- Use QuestDB as the primary time-series database.
- Use UTC hour-bucket `ts` as the designated timestamp across aligned tables.
- Preserve `observed_ts` and `available_ts` for provenance and leakage control.
- Maintain both a unified aligned facts table and a dedicated hourly OHLCV table.
- Add a tested live ETL skeleton before attempting provider-specific production hardening.
- Use ASKGROK as the primary social-sentiment adapter and keep LunarCrush as optional fallback.
- Treat price as the consensus baseline and derivatives positioning as a regime/fragility layer before expanding narrative features.
- Keep the project canonical at 1H for now; do not expand to 30m/15m until 1H data maintenance is reliable.
- Temporarily ignore ASKGROK sentiment in scheduled maintenance to reduce moving parts.
- Prefer Docker Compose for long-running maintenance so the open-source workflow is reproducible outside this Mac.

## Next Step

Stabilize the 1H data maintenance loop:
1. run `astro-abm-maintain-hourly` for recent market/OI/space-weather/ephemeris refreshes
2. run `astro-abm-maintain-daily` for archive overlays such as Binance Vision, GOES X-ray, SWPC recent, and NASA OMNI
3. run `docker compose -f docker-compose.questdb.yml --profile maintenance up -d --build` for the long-running Docker scheduler
4. run `astro-abm-data-completeness` after maintenance and check `health=OK/STALE/MISSING`
5. only after freshness is reliable, build derivatives regime features and feature-quality reports for BTC/ETH

## Resume Anchor

If resuming later, start with:
- .planning/ROADMAP.md
- .planning/HANDOFF.md
- .env.example
- src/astro_abm/etl/maintain_hourly.py
- src/astro_abm/etl/maintain_daily.py
- src/astro_abm/storage/questdb.py

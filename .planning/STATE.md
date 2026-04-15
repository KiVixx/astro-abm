# STATE

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Create a reproducible hourly feature pipeline that lets the system test whether exogenous astro/space-weather signals can explain or perturb simulated market sentiment and agent behavior.
**Current focus:** Phase 5 — ETL Alignment & Automation

## Current Status

- Milestone: MVP hourly data foundation
- Active phase: 5
- Latest artifact: Phase 5 planning initialized
- Verification status: Phase 5 implementation complete, tests passing

## Open Blockers

- No provider credentials configured yet for Polygon/Alpha Vantage/LunarCrush.
- QuestDB has not yet been started in this environment.

## Recent Decisions

- Use QuestDB as the primary time-series database.
- Use UTC hour-bucket `ts` as the designated timestamp across aligned tables.
- Preserve `observed_ts` and `available_ts` for provenance and leakage control.
- Maintain both a unified aligned facts table and a dedicated hourly OHLCV table.

## Next Step

Implement Phase 5 artifacts in the repo:
1. add failing ETL alignment/scheduler tests
2. implement UTC normalization and tradfi forward fill
3. implement merged hourly pipeline helpers and scheduler factory
4. run targeted and full test suites

## Resume Anchor

If resuming later, start with:
- .planning/ROADMAP.md
- .planning/phases/05-etl-alignment-automation/CONTEXT.md
- .planning/phases/05-etl-alignment-automation/PLAN.md

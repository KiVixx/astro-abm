# Phase 5 Plan — ETL Alignment & Automation

Goal: Build the alignment/merge/scheduling layer for the hourly Astro ABM pipeline.

Requirements covered:
- TRAD-03
- ETL-01
- ETL-02
- ETL-03
- ETL-04
- ETL-05

## Work Package 1 — Add failing tests

Files:
- Create: `tests/test_etl.py`

Steps:
1. Write tests for UTC hour normalization of timestamps.
2. Write tests for tradfi forward fill on aligned hourly ranges.
3. Write tests for merging market and feature frames on shared hourly index.
4. Write tests for scheduler factory wiring hourly runs at minute 05.
5. Write tests for transforming DataFrames into QuestDB batch rows.
6. Run tests and confirm failure before implementation.

Success criteria:
- Tests fail because Phase 5 modules do not exist yet.

## Work Package 2 — Implement ETL alignment helpers

Files:
- Create: `src/astro_abm/etl/__init__.py`
- Create: `src/astro_abm/etl/pipeline.py`

Steps:
1. Implement UTC-hour normalization helper.
2. Implement tradfi forward-fill helper.
3. Implement merge helper for aligned hourly frames.
4. Implement row-shaping helper for QuestDB writer inputs.

Success criteria:
- Tests pass for alignment and merge behaviors.

## Work Package 3 — Implement APScheduler orchestration

Files:
- Create: `src/astro_abm/etl/scheduler.py`

Steps:
1. Implement `build_scheduler(job_func, timezone="UTC")`.
2. Register one hourly cron job at minute 05.
3. Use conservative ETL settings: `max_instances=1`, `coalesce=True`, `replace_existing=True`.
4. Keep the scheduler wiring testable without live startup.

Success criteria:
- Scheduler wiring tests pass.

## Work Package 4 — Update docs and state

Files:
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `.planning/STATE.md`

Steps:
1. Add Pandas + APScheduler dependencies.
2. Document the new ETL module layout and scheduler behavior.
3. Update project state after tests pass.

Success criteria:
- Repo documents how hourly ETL alignment and scheduling are intended to work.

## Verification

- `pytest tests/test_etl.py -q`
- `pytest -q`

## Notes

- Use strict TDD.
- Keep ETL orchestration separate from source-specific fetching logic.

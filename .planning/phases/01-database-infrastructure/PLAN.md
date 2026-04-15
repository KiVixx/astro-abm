# Phase 1 Plan — Database & Infrastructure Foundation

Goal: Stand up QuestDB locally and define the first-pass hourly storage schema for Astro ABM.

Requirements covered:
- INF-01
- INF-02
- INF-03

## Work Package 1 — Add local QuestDB runtime config

Files:
- Create: `docker-compose.questdb.yml`

Steps:
1. Add a Docker Compose file using `questdb/questdb:latest`.
2. Expose ports `9000`, `8812`, and `9009`.
3. Persist `/var/lib/questdb` with a named volume.
4. Set container timezone to `UTC`.

Success criteria:
- `docker compose -f docker-compose.questdb.yml up -d` is a valid startup path.

## Work Package 2 — Add QuestDB schema DDL

Files:
- Create: `sql/schema_phase1.sql`

Steps:
1. Define `abm_hourly_facts` with designated timestamp `ts`.
2. Define SYMBOL-based categorical dimensions: `entity_type`, `entity_id`, `source`, `interval`, `asset_class`, `market`, `region`, `metric_name`.
3. Define `market_ohlcv_1h` for efficient 1-hour bar storage.
4. Define an optional metadata dictionary table `abm_entities`.
5. Use `PARTITION BY MONTH` and `WAL`.

Success criteria:
- Schema is syntactically valid QuestDB SQL.
- Tables support both unified features and dedicated OHLCV storage.

## Work Package 3 — Document local startup and schema usage

Files:
- Modify: `README.md`

Steps:
1. Add local setup instructions for QuestDB.
2. Document the meaning of `ts`, `observed_ts`, and `available_ts`.
3. Point developers to the schema file location.

Success criteria:
- README gives enough information to start Phase 1 locally.

## Verification

Run when Docker is available:
- `docker compose -f docker-compose.questdb.yml config`
- `docker compose -f docker-compose.questdb.yml up -d`
- open `http://localhost:9000`
- apply `sql/schema_phase1.sql` through QuestDB UI or PG wire client

## Notes

- Keep this phase infra-only.
- Do not start implementing provider-specific ingestion in this phase.

# Phase 1 Context — Database & Infrastructure Foundation

## Goal

Set up the local QuestDB foundation for the Astro ABM MVP and define schemas that can store all aligned 1-hour data sources in UTC.

## Scope

In scope:
- QuestDB Docker startup configuration
- SQL schema for unified aligned facts table
- SQL schema for dedicated hourly OHLCV table
- Basic repo documentation for local startup

Out of scope:
- Provider-specific Python ingestion code
- APScheduler automation
- Any minute-level data handling
- Agent simulation logic

## Key Constraints

- `ts` must represent 1-hour UTC bucket start.
- QuestDB tables should use SYMBOL aggressively for repeated categorical fields.
- Tables should preserve `observed_ts` and `available_ts`.
- Monthly partitioning is acceptable for MVP hourly data volume.

## Assumptions

- Local development will use Docker.
- QuestDB default ports 9000/8812/9009 are acceptable.
- MVP queries will need both unified feature access and efficient OHLCV retrieval.

## Acceptance Expectations

- A new developer can clone repo and start QuestDB from checked-in config.
- Schema file is executable from QuestDB SQL console or PG wire client.
- The table design is compatible with upcoming ETL phases.

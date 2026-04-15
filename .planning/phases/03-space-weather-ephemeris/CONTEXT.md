# Phase 3 Context — Space Weather & Ephemeris Feature Layer

## Goal

Implement the astro-exogenous feature layer for the MVP by ingesting NOAA SWPC space-weather data and computing local ephemeris-derived hourly features with pyswisseph.

## Scope

In scope:
- NOAA SWPC client/parsers for solar wind speed, IMF Bz, GOES X-ray flux, and Kp index
- 3-hour Kp to hourly alignment logic
- Ephemeris calculator from UTC datetimes using pyswisseph
- Moon phase percentage calculation
- Relative angular feature calculation for major planets
- Normalized feature rows suitable for `abm_hourly_facts`

Out of scope:
- APScheduler automation
- QuestDB generic feature writer for all domains beyond simple row shaping
- Social sentiment ingestion
- Agent simulation behavior

## Key Constraints

- All features must align to UTC hour buckets.
- NOAA SWPC endpoints are heterogeneous in response shape and must be parsed explicitly.
- Kp index is natively 3-hour cadence and needs deterministic hourly expansion/alignment.
- Ephemeris calculations must be local and should not depend on network APIs.
- Feature outputs must preserve provenance (`source`, `observed_ts`, `available_ts`).

## Assumptions

- `pyswisseph` / `swisseph` will be available in the runtime environment or injected in tests.
- For MVP, longitude-based angular separations are sufficient as planetary relative features.
- Space-weather features can initially target a `GLOBAL` entity and `macro` asset class.

## Acceptance Expectations

- Project contains tested code for NOAA SWPC parsing and feature normalization.
- Project contains tested code for moon phase percentage and relative angular features from UTC timestamps.
- The code can generate rows ready to insert into the unified hourly facts table.

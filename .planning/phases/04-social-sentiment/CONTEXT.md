# Phase 4 Context — Social Sentiment Validation Layer

## Goal

Implement the crypto social-sentiment ingestion layer using LunarCrush so the MVP can compare external social activity and sentiment against astro/space-weather feature shifts.

## Scope

In scope:
- LunarCrush client for asset-level hourly time-series retrieval
- Parsing and normalization of hourly social volume and sentiment metrics
- Symbol-aligned feature row shaping for `abm_hourly_facts`
- Tests for payload parsing, UTC hour normalization, and feature-row generation

Out of scope:
- APScheduler automation
- Live model calibration logic
- Social feature joins with other domains
- Any non-crypto sentiment providers

## Key Constraints

- Output must align to UTC hourly buckets.
- Symbol mapping should stay crypto-oriented and explicit.
- Parser must be defensive because LunarCrush response shapes may vary by plan/version.
- Feature rows must preserve provenance and availability timestamps.

## Assumptions

- LunarCrush API key will be provided later via environment variable.
- Hourly payloads expose a `timeSeries`-like structure with unix timestamps.
- `social_volume` and a sentiment score field are the core MVP metrics.

## Acceptance Expectations

- Repo contains tested code that can normalize hourly LunarCrush social metrics.
- Output rows are ready for insertion into the unified hourly facts table.
- The social feature layer is symbol-scoped and UTC-normalized.

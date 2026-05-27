# Astro ABM Scenario Platform MVP

## Product Purpose

Astro ABM Scenario Platform MVP is a local-first AI market scenario simulation
platform based on astro-abm daily research data.

The product is designed for scenario rehearsal, not market prediction. It lets
users combine daily market / macro / astro research context with simple agent
profiles and generate cautious scenario reports for review.

Every MVP report must state:

- association only
- scenario rehearsal only
- not financial advice
- not a trading signal

## Core User Flows

1. Search simulations.
2. Create a simulation.
3. Select agents.
4. Select an LLM provider.
5. Generate a report.
6. Save the report locally.
7. View the saved report.

## MVP Scope

Included in this first product layer:

- Daily data only.
- Local JSON / Markdown storage only.
- Mock deterministic simulation engine.
- Default local agent profiles.
- Optional OpenAI-compatible configuration surface without required network
  calls.
- Local-first reports under `astro_research/output/scenarios/`.

Explicitly not included:

- No auth.
- No payment.
- No public SaaS deployment.
- No live trading.
- No order book simulation.
- No causal claims.
- No trading signals.
- No external LLM dependency for tests.

## Core Entities

### ScenarioSpec

User-provided scenario input: title, date range, assets, selected agents,
visibility metadata, and LLM provider preference.

### AgentProfile

A reusable model of an agent group. MVP agents are broad archetypes rather than
specific people, institutions, or companies.

### SimulationRun

The deterministic execution of one scenario spec against selected agents and a
daily context placeholder.

### ScenarioReport

Saved output containing the scenario metadata, daily context, agent behavior
summaries, risks, caveats, provenance, Markdown report, and disclaimer.

## Recommended Initial Agents

- `crypto_retail_fomo`
- `long_term_holder`
- `leveraged_trader`
- `macro_allocator`
- `big_tech_company_type`
- `global_bank_type`
- `energy_company_type`

## Future Agents, Not MVP

- World top 100 companies.
- Specific company agents.
- Social-media narrative agents.
- Institutional desk agents.

## Storage Boundary

Generated scenario reports are written to:

```text
astro_research/output/scenarios/
```

The directory is git-ignored except `.gitkeep`. Scenario JSON and Markdown files
are generated artifacts and should not be committed.

## Safety Boundaries

The MVP must never present a report as investment advice, a trading signal, a
causal prediction, or a statement of forecasting accuracy. The API should return
structured reports that are useful for scenario thinking while preserving those
boundaries.

## Acceptance Criteria

- Documentation exists.
- MVP boundaries are clear.
- Disclaimers are explicit.
- Local API can create, list, and load scenario reports.
- Scenario reports can be generated without external LLM calls.

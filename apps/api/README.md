# Astro ABM API

Local-first scenario simulation API for the Astro ABM product MVP.

Run locally:

```bash
make api
```

Create a deterministic demo scenario:

```bash
make scenario-demo
```

Run product smoke checks:

```bash
make product-smoke
```

Scenario reports are saved as JSON and Markdown under:

```text
astro_research/output/scenarios/
```

Override the output directory for tests or local experiments:

```bash
ASTRO_ABM_SCENARIO_OUTPUT_DIR=/tmp/astro-abm-scenarios make scenario-demo
```

The MVP uses the mock provider by default. `openai_compatible` is represented as
a typed interface for future Ollama or cloud LLM usage, but PR1 does not perform
external LLM calls.

Every report is association only, scenario rehearsal only, not financial advice,
and not a trading signal.

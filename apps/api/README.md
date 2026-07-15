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

`GET /scenarios` returns lightweight `ScenarioSummary` records, including
compact worldline status, generation mode, failed-chunk count, and coverage
counts. It never returns the full Markdown or daily timeline. Use
`GET /scenarios/{scenario_id}` only when opening one report or Workbench.

Scenario JSON and Markdown updates use same-directory temporary files followed
by atomic replacement. If the API process stops during a chunk update, readers
continue to see the previous complete file rather than a truncated report.
JSON is the canonical API record; an interruption between the two replacements
can leave Markdown one revision behind until the next successful save.

Override the output directory for tests or local experiments:

```bash
ASTRO_ABM_SCENARIO_OUTPUT_DIR=/tmp/astro-abm-scenarios make scenario-demo
```

The API uses the mock provider by default. `openai_compatible` supports
OpenAI-compatible chat-completions endpoints, including local providers such as
Ollama, LM Studio, or vLLM when they expose an OpenAI-compatible API. Real LLM
calls are opt-in. The web create form can enable them per scenario and pass a
base URL, model, and optional API key for that request only.

For API-only usage, the backend can also use environment defaults:

```bash
ASTRO_ABM_ENABLE_REAL_LLM=1
ASTRO_ABM_LLM_BASE_URL=http://localhost:11434/v1
ASTRO_ABM_LLM_MODEL=your-local-model
ASTRO_ABM_LLM_API_KEY=optional-or-provider-key
ASTRO_ABM_LLM_TIMEOUT_SECONDS=120
ASTRO_ABM_LLM_MAX_OUTPUT_TOKENS=5000
```

If real calls are disabled, `openai_compatible` scenario creation records a
safe `dry_run` LLM report. API keys from either the request or environment are
never saved into scenario JSON, Markdown, logs, or provenance.

Every report is association only, scenario rehearsal only, not financial advice,
and not a trading signal.

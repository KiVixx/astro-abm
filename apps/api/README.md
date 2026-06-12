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

The API uses the mock provider by default. `openai_compatible` supports
OpenAI-compatible chat-completions endpoints, including local providers such as
Ollama, LM Studio, or vLLM when they expose an OpenAI-compatible API. Real LLM
calls are opt-in and disabled unless the API server has:

```bash
ASTRO_ABM_ENABLE_REAL_LLM=1
ASTRO_ABM_LLM_BASE_URL=http://localhost:11434/v1
ASTRO_ABM_LLM_MODEL=your-local-model
ASTRO_ABM_LLM_API_KEY=optional-or-provider-key
```

If real calls are disabled, `openai_compatible` scenario creation records a
safe `dry_run` LLM report. API keys are read from environment variables and are
never saved into scenario JSON, Markdown, logs, or provenance.

Every report is association only, scenario rehearsal only, not financial advice,
and not a trading signal.

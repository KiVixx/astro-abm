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

## Accounts and ownership

Anonymous visitors can create public Worldlines in a temporary Guest workspace.
Local accounts can create private Worldlines, and ownership controls deletion,
chunk generation, and regeneration. Account/session state is stored in the
ignored SQLite file `.local/astro_abm_accounts.sqlite3` by default.

Worldline cards support canonical JSON export. Logged-in users can import a
verified export from the Account page; imports always receive a new server ID.
See `docs/product/public_alpha_accounts.md` for ACL rules, retention, limits,
production requirements, and the deferred wallet/IPFS path.

`GET /scenarios` returns lightweight `ScenarioSummary` records, including
compact worldline status, generation mode, failed-chunk count, and coverage
counts. It never returns the full Markdown or daily timeline. Use
`GET /scenarios/{scenario_id}` only when opening one report or Workbench.
Fallback summaries distinguish configuration-only fallback chunks from chunks
where an enabled LLM call or output actually failed.

Scenario JSON and Markdown updates use same-directory temporary files followed
by atomic replacement. If the API process stops during a chunk update, readers
continue to see the previous complete file rather than a truncated report.
JSON is the canonical API record; an interruption between the two replacements
can leave Markdown one revision behind until the next successful save.
Atomic updates preserve the permissions of existing report files.
The list endpoint skips an unreadable legacy report and logs only its filename
and a safe error category; report contents and validation values are not logged.
Opening an unreadable report returns HTTP `422` with the same safe category
instead of exposing raw JSON or schema-validation values.

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
ASTRO_ABM_LLM_MAX_OUTPUT_TOKENS=32000
```

If real calls are disabled, `openai_compatible` scenario creation records a
safe `dry_run` LLM report. API keys from either the request or environment are
never saved into scenario JSON, Markdown, logs, or provenance.

Every report is association only, scenario rehearsal only, not financial advice,
and not a trading signal.

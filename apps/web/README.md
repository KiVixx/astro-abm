# Astro ABM Web

Next.js frontend for the local-first Astro ABM Worldline Simulator.

Run the API first:

```bash
make api
```

Then run the web app:

```bash
make web
```

Defaults:

- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3000`

If a port is already occupied:

```bash
make api API_PORT=18000
make web WEB_PORT=13000 API_PORT=18000
```

The frontend calls the FastAPI API through `NEXT_PUBLIC_ASTRO_ABM_API_BASE_URL`.
If unset, it defaults to `http://localhost:8000`.

Primary product routes:

- `/worldlines` explores saved simulated worldlines.
- `/worldlines/new` creates a worldline through the existing scenario API.
- `/worldlines/{id}` opens the Worldline Workbench and daily playback console.
- `/scenarios/{id}/report` opens the full saved report.

Scenario remains the API/storage entity. Worldline is the primary product
experience layered on top of the saved scenario report. Simulated causal links
are scenario-internal rehearsal links only; they are not real-world causal proof,
not forecasts, and not trading signals.

This UI is association only, scenario rehearsal only, not financial advice, and
not a trading signal.

# Astro ABM Web

Next.js frontend for the local-first Astro ABM Scenario Platform MVP.

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

This UI is association only, scenario rehearsal only, not financial advice, and
not a trading signal.

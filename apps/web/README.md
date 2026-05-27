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

The frontend calls the FastAPI API through `NEXT_PUBLIC_ASTRO_ABM_API_BASE_URL`.
If unset, it defaults to `http://localhost:8000`.

This UI is association only, scenario rehearsal only, not financial advice, and
not a trading signal.

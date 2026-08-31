# Cloudflare Tunnel Deployment

This deployment keeps Astro ABM bound to localhost and exposes it through a
Cloudflare Tunnel. The Web app and API remain separate origins:

- `https://example.com` -> `http://127.0.0.1:3000`
- `https://www.example.com` -> `http://127.0.0.1:3000`
- `https://api.example.com` -> `http://127.0.0.1:8000`

## Production Environment

Keep production values in an ignored file with mode `0600`. At minimum set:

```dotenv
ASTRO_ABM_ENV=production
ASTRO_ABM_ALLOWED_ORIGINS=https://example.com,https://www.example.com
ASTRO_ABM_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128
ASTRO_ABM_RATE_LIMIT_SALT=<long-random-value>
NEXT_PUBLIC_ASTRO_ABM_API_BASE_URL=https://api.example.com
NEXT_PUBLIC_ASTRO_ABM_SOURCE_URL=https://github.com/KiVixx/astro-abm
```

Also configure explicit absolute paths for mutable local state, including the
scenario directory, account database, research output root, preset directory,
and custom market-series storage. Never place API keys or Tunnel tokens in Git.

## Build And Run

Install dependencies and build the Web bundle:

```bash
uv sync --extra dev
npm --prefix apps/web ci
make web-build
```

Run the API and Web server in separate supervised processes:

```bash
make api-production
make web-production
```

Run `cloudflared tunnel run --token ...` as a third supervised process. Use a
service manager such as launchd or systemd so all three processes restart after
a host reboot. Bind the origin services to `127.0.0.1`; do not expose ports 3000
or 8000 directly to the Internet.

## Verification

Verify the public deployment before announcing it:

```bash
curl -fsS https://api.example.com/health
curl -fsSI https://example.com/
curl -fsSI https://www.example.com/
```

Also verify browser CORS preflight, account registration/login/logout, public
and private Worldline visibility, and scenario generation in deterministic mock
mode. Real LLM calls remain opt-in and API credentials must never be persisted
in scenario reports.

Cloudflare provides the network edge, but application limits remain necessary.
Keep the request-size, rate-limit, storage-capacity, and generation-concurrency
controls documented in
[`ddos_abuse_protection.md`](ddos_abuse_protection.md) enabled.

# Public Alpha Accounts and Worldline Ownership

## Purpose

Astro ABM uses a Web-first account layer before adding wallet identity or
on-chain publication. The internal user UUID is the stable identity. Password,
OAuth, and wallet identities can later attach to that UUID without changing
Worldline ownership.

## Current model

- Anonymous visitors receive an opaque Guest workspace cookie.
- Guest-created Worldlines are always public.
- A logged-in user may create public or private Worldlines.
- Private Worldlines are readable and mutable only by their owner.
- Public Worldlines are readable by everyone but mutable only by their owner.
- Registering or logging in claims Worldlines created by the current Guest workspace.
- Legacy public reports remain readable but are read-only. Legacy private reports
  without ownership metadata are hidden.

Passwords are hashed with Argon2id. Session and CSRF tokens are random opaque
values; only token hashes are stored in the local SQLite account database.
Session cookies are HttpOnly and become Secure in production. State-changing
authenticated requests require the matching CSRF token.

## Alpha limits and retention

```text
ASTRO_ABM_GUEST_TTL_DAYS=30
ASTRO_ABM_GUEST_SCENARIO_QUOTA=20
ASTRO_ABM_USER_SCENARIO_QUOTA=200
ASTRO_ABM_CREATE_RATE_PER_HOUR=60
ASTRO_ABM_LLM_RATE_PER_HOUR=240
```

Run `make cleanup-guests` periodically to remove expired, unclaimed Guest
workspaces and their reports. It never modifies research stores.

## Portability

Worldline cards export a versioned canonical JSON envelope. Its SHA-256 hash is
computed from sorted compact UTF-8 JSON. Import verifies the hash and always
creates a new server-generated ID. The hash verifies artifact integrity; it
does not prove authorship, market accuracy, causality, or investment value.

## Deployment requirements

1. Set `ASTRO_ABM_ENV=production` and serve API/Web through HTTPS.
2. Set `ASTRO_ABM_ALLOWED_ORIGINS` to the exact Web origins.
3. Persist and back up `.local/astro_abm_accounts.sqlite3` outside Git.
4. Run Guest cleanup on a schedule.
5. Keep LLM keys in backend environment variables where possible. Request keys
   are relayed only for that request and are never written to reports.
6. Put request/body limits and operational monitoring in front of the API.

The current alpha deliberately has no password recovery and no OAuth provider.
Do not present it as a production identity service until recovery or external
identity verification, monitoring, and backup/restore drills exist.

## Deferred Web3 path

Wallet sign-in, IPFS replication, and optional on-chain content-hash anchoring
remain future extensions. Public Worldline content does not need to be stored
directly on Ethereum. The canonical export hash is the compatibility foundation
for optional wallet signatures or hash anchoring later.

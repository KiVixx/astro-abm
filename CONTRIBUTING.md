# Contributing To Astro ABM

Thank you for helping improve Astro ABM.

## Before Opening A Change

1. Open an issue for substantial product, data-source, schema, or licensing
   changes.
2. Keep each pull request focused and include tests appropriate to its risk.
3. Do not commit API keys, `.env`, local data, generated reports, database
   volumes, Parquet snapshots, LLM presets, `.next`, or `node_modules`.
4. Do not add market data unless its redistribution rights are documented and
   explicitly approved.
5. Preserve the product's scenario-rehearsal and non-causal wording.

## Development Checks

Run from the repository root:

```bash
make test
make product-smoke
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
git diff --check
```

## Contribution License

Unless explicitly agreed otherwise in writing, contributions are submitted
under the same `AGPL-3.0-or-later` terms as the project. Contributors retain
copyright in their contributions.

This repository does not currently require contributors to grant broader
proprietary relicensing rights. If the project later adopts dual licensing, it
must obtain the permissions needed for affected external contributions rather
than assuming that a normal pull request grants those rights.

By submitting a contribution, you represent that you have the right to provide
it under these terms and that it does not knowingly include incompatible code,
restricted data, or confidential material.

## Reporting Security Issues

Do not place credentials or sensitive details in a public issue. Follow
[`SECURITY.md`](SECURITY.md) instead.

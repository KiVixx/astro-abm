# Dependency License Audit

Audit date: 2026-07-18

This is a release-engineering snapshot, not a legal opinion. Dependency terms
can change when lockfiles change, so maintainers must regenerate the inventory
for every public release.

## Project License

- Root source: `AGPL-3.0-or-later`
- Python package metadata: `AGPL-3.0-or-later`
- Web package metadata: `AGPL-3.0-or-later`

## Python Environment

The resolved local environment contained 51 third-party distributions. Most
reported MIT, BSD, Apache, PSF, or similarly permissive licenses. Items needing
explicit notice or periodic review included:

| Dependency | Reported license | Review note |
| --- | --- | --- |
| `pyswisseph` | GNU Affero General Public License v3 | Core ephemeris dependency; Astro ABM uses the AGPL path. |
| `psycopg` / `psycopg-binary` | LGPL-3.0-only | Copyleft library terms remain applicable. |
| `certifi` | MPL-2.0 | File-level copyleft terms remain applicable. |
| `python-dateutil` | Dual license | Confirm the upstream license selection in release notices when packaging. |

No obvious dependency-license blocker to an AGPL release was found in this
metadata review. Package metadata can be incomplete and must not be treated as
the sole legal record.

## Web Environment

The npm inventory contained 45 packages at audit time:

| Reported license | Package count |
| --- | ---: |
| MIT | 22 |
| ISC | 12 |
| Apache-2.0 | 5 |
| BSD-3-Clause | 2 |
| 0BSD | 1 |
| CC-BY-4.0 | 1 |
| LGPL-3.0-or-later | 1 |
| Project package metadata | 1 |

The LGPL item was the platform-specific `@img/sharp-libvips-darwin-arm64`
binary dependency used by the Next.js image toolchain. Preserve its upstream
notices when distributing a bundle that includes it.

## Data And Services

Software dependency compatibility does not grant rights to redistribute Yahoo
Finance, LBMA / ICE, FRED third-party series, exchange data, or local research
CSVs. See `DATA_LICENSE.md` and `THIRD_PARTY_NOTICES.md`.

## Reproduction Notes

Python license metadata was inspected from the locked `uv` environment using
`importlib.metadata`. npm licenses were inspected from the locked Web install.
The repository-level audit is available as:

```bash
make open-source-audit
```

For a formal commercial release, use a dedicated software-composition-analysis
tool and obtain qualified review of reciprocal licenses and data-provider terms.

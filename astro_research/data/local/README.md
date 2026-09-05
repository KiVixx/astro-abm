# Local Research Data

## Hong Kong Mark Six

`make marksix-maintain` creates `marksix/marksix.sqlite3` locally. The database
is intentionally ignored by Git. Number records cover 1976 onward. The legacy
1976–1992 rows lack exact dates; complete dated history begins on 1993-01-05,
and recent results are refreshed from HKJC. Source data terms remain
separate from the repository's AGPL software license.

This directory is reserved for local CSV datasets that cannot be committed to
the repository because of size, licensing, or provenance constraints.

Large files under `astro_research/data/local/` are git-ignored. Keep only small
schema examples in git.

`LOCAL_DATA_PROVENANCE.json` is the commit-safe manifest for local long-history
inputs. It must be updated whenever SPX, Gold, DXY, or the credit proxy CSVs are
refreshed. Do not commit the referenced CSVs.

Required provenance fields per series:

- `source`
- `provider`
- `original_symbol_or_series`
- `retrieval_method`
- `retrieved_at`
- `coverage_start`
- `coverage_end`
- `original_frequency`
- `transformed_frequency`
- `fill_method`
- `license_note`
- `redistribution_allowed`
- `publication_grade`
- `is_canonical`
- `is_proxy`
- `is_provisional`
- `caveats`

Use explicit caveats for local-only data, licensing review, proxy
substitutions, provisional status, and any transformed frequency or fill method.

## HY OAS Fallback

Expected path:

`astro_research/data/local/credit/hy_oas_daily.csv`

Expected columns:

- `date` or `ts`
- `value`

The value should be either the daily high-yield option-adjusted spread in
percent, or a clearly documented credit-spread proxy. The current fallback
script generates a `BAA_MINUS_AAA` proxy and records that caveat in
`LOCAL_DATA_PROVENANCE.json`.

## Price CSV Schema

See `examples/spx_daily.example.csv`, `examples/gold_daily.example.csv`, and
`examples/dxy_daily.example.csv`.

Required columns:

- `date` or `ts`
- `close`

Optional columns:

- `open`
- `high`
- `low`
- `adj_close`
- `volume`

## Indicator CSV Schema

See `examples/hy_oas_daily.example.csv`.

Required columns:

- `date` or `ts`
- `value`

## How to refresh these files

The raw CSV files in this directory are not committed, but the repo includes a
best-effort fetch helper for maintainers:

```bash
uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms
```

The command writes the ignored CSV files and refreshes an ignored local
provenance manifest by default:

```text
astro_research/data/local/LOCAL_DATA_PROVENANCE.local.json
```

This keeps `git status` clean for a fresh clone. Maintainers can deliberately
refresh the tracked commit-safe manifest with:

```bash
uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms --provenance-mode tracked
```

You can fetch a single series:

```bash
uv run python scripts/astro_abm_ops.py fetch-local-data --asset SPX --accept-research-local-terms
uv run python scripts/astro_abm_ops.py fetch-local-data --asset Gold --accept-research-local-terms
uv run python scripts/astro_abm_ops.py fetch-local-data --asset DXY --accept-research-local-terms
uv run python scripts/astro_abm_ops.py fetch-local-data --asset CreditProxy --accept-research-local-terms
```

`CreditProxy` requires `FRED_API_KEY` in `.env`.

## Source methods used by this project

| Local file | Series | Method |
|---|---|---|
| `equity/spx_daily.csv` | SPX / S&P 500 | Yahoo Finance chart endpoint, symbol `^GSPC`, daily OHLCV |
| `fx/dxy_daily.csv` | DXY / US Dollar Index | Yahoo Finance chart endpoint, symbol `DX-Y.NYB`, daily OHLCV |
| `commodities/gold_daily.csv` | Gold USD | LBMA `gold_pm.json` as primary, `gold_am.json` as fallback when PM is missing |
| `credit/hy_oas_daily.csv` | CreditProxy | FRED `BAA - AAA`, monthly observations expanded to business-daily by forward fill |

Important caveats:

- Yahoo-derived SPX/DXY files are local research inputs. Do not redistribute
  the generated CSV from this repo without reviewing Yahoo licensing.
- LBMA/ICE gold benchmark data needs licensing review before publication or
  redistribution.
- `CreditProxy` is **not** true ICE/BofA High Yield OAS. It is a transparent
  BAA-minus-AAA corporate yield spread proxy used when long HY OAS history is
  unavailable.

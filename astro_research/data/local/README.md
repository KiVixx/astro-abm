# Local Research Data

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

The value should be the daily high-yield option-adjusted spread in percent.

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

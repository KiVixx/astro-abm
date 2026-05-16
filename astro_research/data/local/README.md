# Local Research Data

This directory is reserved for local CSV datasets that cannot be committed to
the repository because of size, licensing, or provenance constraints.

Large files under `astro_research/data/local/` are git-ignored. Keep only small
schema examples in git.

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

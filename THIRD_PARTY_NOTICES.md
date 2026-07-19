# Third-Party Notices

Astro ABM depends on third-party software and optional data services. Their
licenses and terms remain independent of the project's AGPL license.

## Swiss Ephemeris / pyswisseph

Swiss Ephemeris is developed by Astrodienst AG and contributors. Astro ABM
uses it through the `pyswisseph` Python package and follows the AGPL licensing
path. See [`LICENSE_NOTES.md`](LICENSE_NOTES.md) and the upstream documentation:

- https://www.astro.com/swisseph/
- https://www.astro.com/swisseph-download/doc/swisseph.htm
- https://github.com/aloistr/swisseph

Ephemeris data files may have additional notices or terms. Do not assume that
the Astro ABM software license grants redistribution rights to those files.

## FRED

Optional market and macroeconomic data may be retrieved through the Federal
Reserve Bank of St. Louis FRED API.

> This product uses the FRED® API but is not endorsed or certified by the
> Federal Reserve Bank of St. Louis.

Users of FRED-backed features must review and comply with the current FRED API
Terms of Use: https://fred.stlouisfed.org/docs/api/terms_of_use.html

Some series available through FRED are owned or licensed by third parties and
may carry additional restrictions.

## Yahoo Finance, LBMA / ICE, And Other Data Providers

Local research workflows can optionally use data obtained from Yahoo Finance,
LBMA / ICE Benchmark Administration, exchanges, and other providers. Astro ABM
does not redistribute those real local files. Provider names identify sources
only and do not imply endorsement.

Review [`DATA_LICENSE.md`](DATA_LICENSE.md) and the source-specific provenance
metadata before publishing or commercializing derived outputs.

## Dependency Inventory

Python and JavaScript dependency versions are pinned or resolved in `uv.lock`
and `apps/web/package-lock.json`. Those packages retain their own licenses and
copyright notices. Release maintainers should regenerate a dependency-license
report before each public release.

This notice is informational and may not enumerate every transitive dependency.

from __future__ import annotations

from typing import Any

from astro_abm_api.models.scenario import ScenarioCreateRequest


def build_daily_context(request: ScenarioCreateRequest) -> dict[str, Any]:
    """Return the MVP daily context placeholder.

    This boundary is intentionally small so later PRs can replace it with
    DuckDB/Parquet reads without changing the public API contract.
    """
    return {
        "data_layer": "daily",
        "date_range": {
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
        },
        "assets": request.assets,
        "available_inputs": [
            "daily_ephemeris",
            "financial_stress_daily",
            "market_daily",
            "macro_daily",
        ],
        "notes": [
            "MVP uses daily association context only.",
            "This version does not perform point-in-time backtesting.",
        ],
    }

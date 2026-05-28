from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from astro_abm_api.models.report import DailyAstroContext, DailyMarketContext
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


def iter_calendar_days(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def build_placeholder_daily_contexts(request: ScenarioCreateRequest) -> list[dict[str, Any]]:
    """Build deterministic daily placeholders for the requested date range."""
    stress_regimes = ["calm", "watchful", "elevated"]
    volatility_regimes = ["compressed", "normal", "expanded"]
    liquidity_regimes = ["orderly", "selective", "thin"]
    astro_intensities = ["low", "medium", "high"]
    astro_tags = [
        ["daily_ephemeris_placeholder"],
        ["moon_phase_placeholder", "aspect_context_placeholder"],
        ["station_window_placeholder", "aspect_cluster_placeholder"],
    ]

    contexts: list[dict[str, Any]] = []
    for day_index, current_date in enumerate(
        iter_calendar_days(request.start_date, request.end_date), start=1
    ):
        selector = (day_index - 1) % 3
        stress_regime = stress_regimes[selector]
        volatility_regime = volatility_regimes[(day_index + 1) % 3]
        liquidity_regime = liquidity_regimes[(day_index + 2) % 3]
        intensity = astro_intensities[selector]
        tags = astro_tags[selector]
        contexts.append(
            {
                "date": current_date,
                "day_index": day_index,
                "astro_context": DailyAstroContext(
                    summary=(
                        f"Placeholder daily astro context for {current_date.isoformat()} "
                        f"using deterministic {intensity} intensity tags."
                    ),
                    event_tags=tags,
                    intensity=intensity,
                ),
                "market_context": DailyMarketContext(
                    summary=(
                        f"Placeholder market context marks stress as {stress_regime}, "
                        f"volatility as {volatility_regime}, and liquidity as {liquidity_regime}."
                    ),
                    stress_regime=stress_regime,
                    volatility_regime=volatility_regime,
                    liquidity_regime=liquidity_regime,
                ),
                "daily_risk_themes": [
                    f"{stress_regime}_stress_review",
                    f"{volatility_regime}_volatility_awareness",
                    f"{liquidity_regime}_liquidity_planning",
                ],
                "daily_summary": (
                    f"Day {day_index} is a placeholder daily association snapshot for "
                    f"{', '.join(request.assets)}. It rehearses narrative, stress, "
                    "volatility, and liquidity context without making a directional call."
                ),
                "confidence": "low_placeholder_confidence",
                "caveats": [
                    "Daily context is placeholder data until real daily research data is connected.",
                    "This snapshot does not read DuckDB, Parquet, or external APIs.",
                ],
            }
        )
    return contexts

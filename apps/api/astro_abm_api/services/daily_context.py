from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from astro_abm_api.models.report import DailyAstroContext, DailyMarketContext
from astro_abm_api.models.scenario import ScenarioCreateRequest
from astro_abm_api.services.daily_research_context import DailyResearchContextProvider


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


def stress_risk_theme(stress_regime: str) -> str:
    if stress_regime == "stress":
        return "elevated_stress_review"
    return f"{stress_regime}_stress_review"


def snapshot_kind(source: str) -> str:
    if source == "local_research_snapshot":
        return "read-only daily research context snapshot"
    return "placeholder daily association snapshot"


def confidence_label(data_quality: str) -> str:
    if data_quality == "local_research_available":
        return "low_research_context_confidence"
    if data_quality == "partial_local_research_available":
        return "low_association_confidence"
    return "low_placeholder_confidence"


def astro_event_tags(
    placeholder_tags: list[str],
    *,
    astro_daily_status: str,
    astro_activity: str,
) -> list[str]:
    if astro_daily_status == "available":
        return ["local_astro_daily", f"astro_activity:{astro_activity}"]
    return placeholder_tags


def build_placeholder_daily_contexts(
    request: ScenarioCreateRequest,
    provider: DailyResearchContextProvider | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic daily contexts with optional local research tags."""
    research_provider = provider or DailyResearchContextProvider()
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
        research_context = research_provider.context_for_date(
            current_date,
            assets=request.assets,
            fallback_stress_regime=stress_regime,
            fallback_volatility_regime=volatility_regime,
            fallback_liquidity_regime=liquidity_regime,
            fallback_astro_activity=intensity,
        )
        stress_regime = research_context.signals.stress_regime
        volatility_regime = research_context.signals.volatility_regime
        liquidity_regime = research_context.signals.liquidity_regime
        intensity = research_context.signals.astro_activity
        tags = astro_event_tags(
            tags,
            astro_daily_status=research_context.coverage.astro_daily,
            astro_activity=intensity,
        )
        kind = snapshot_kind(research_context.coverage.source)
        confidence = confidence_label(research_context.signals.data_quality)
        contexts.append(
            {
                "date": current_date,
                "day_index": day_index,
                "astro_context": DailyAstroContext(
                    summary=(
                        f"Daily astro context for {current_date.isoformat()} uses "
                        f"{intensity} activity tags from local research when available, "
                        "otherwise deterministic placeholder tags."
                    ),
                    event_tags=tags,
                    intensity=intensity,
                ),
                "market_context": DailyMarketContext(
                    summary=(
                        f"Daily market context marks stress regime: {stress_regime}, "
                        f"volatility regime: {volatility_regime}, and liquidity regime: {liquidity_regime}; "
                        "tags are read-only local research context when available."
                    ),
                    stress_regime=stress_regime,
                    volatility_regime=volatility_regime,
                    liquidity_regime=liquidity_regime,
                ),
                "daily_risk_themes": [
                    stress_risk_theme(stress_regime),
                    f"{volatility_regime}_volatility_awareness",
                    f"{liquidity_regime}_liquidity_planning",
                ],
                "daily_summary": (
                    f"Day {day_index} is a {kind} for "
                    f"{', '.join(request.assets)}. It rehearses narrative, stress, "
                    "volatility, and liquidity context without making a directional call."
                ),
                "confidence": confidence,
                "caveats": [
                    "Daily context is read-only association context; it is not point-in-time backtesting.",
                    "If local research data is unavailable, deterministic placeholder tags are retained.",
                    "This snapshot never fetches external APIs or mutates research stores.",
                ],
                "data_coverage": research_context.coverage,
                "research_signals": research_context.signals,
            }
        )
    return contexts

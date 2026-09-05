from __future__ import annotations

from fastapi import APIRouter, Query

from astro_abm.marksix import (
    HISTORY_URL,
    LEGACY_HISTORY_URL,
    OFFICIAL_PAGE,
    database_status,
    generate_worldlines,
    list_draws,
    number_frequencies,
)
from astro_abm.marksix_astro import CURRENT_RULE_START, MOTION_CONDITIONS, SUPPORTED_BODIES, analyze_retrograde_numbers
from astro_abm_api.models.marksix import (
    MarkSixDrawRecord,
    MarkSixFrequency,
    MarkSixStatus,
    MarkSixWorldlineRequest,
    MarkSixWorldlineResponse,
    MarkSixAstroResearch,
)


router = APIRouter(prefix="/marksix", tags=["marksix"])


@router.get("/status", response_model=MarkSixStatus)
def get_marksix_status() -> MarkSixStatus:
    status = database_status()
    return MarkSixStatus(
        total_draws=status["total_draws"],
        coverage_start=status["coverage_start"],
        coverage_end=status["coverage_end"],
        official_verified_draws=status["official_verified_draws"],
        history_start_year=status["history_start_year"],
        legacy_draws_without_dates=status["legacy_draws_without_dates"],
        historical_source=HISTORY_URL,
        legacy_historical_source=LEGACY_HISTORY_URL.format(year=1976),
        official_source=OFFICIAL_PAGE,
        coverage_note=(
            "Number records cover 1976 onward. The 1976-1992 legacy archive provides year and draw "
            "number but no reliable draw date; complete dated records begin in 1993."
        ),
    )


@router.get("/draws", response_model=list[MarkSixDrawRecord])
def get_marksix_draws(limit: int = Query(default=20, ge=1, le=200)) -> list[MarkSixDrawRecord]:
    return [MarkSixDrawRecord.model_validate(row) for row in list_draws(limit=limit)]


@router.get("/frequencies", response_model=list[MarkSixFrequency])
def get_marksix_frequencies() -> list[MarkSixFrequency]:
    return [MarkSixFrequency.model_validate(row) for row in number_frequencies()]


@router.get("/astro-research", response_model=MarkSixAstroResearch)
def get_marksix_astro_research(
    body: str = Query(default="Mercury"),
    condition: str = Query(default="retrograde"),
    number_role: str = Query(default="main", pattern="^(main|extra)$"),
    start_date: str = Query(default=CURRENT_RULE_START, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> MarkSixAstroResearch:
    normalized_body = body.strip().title()
    if normalized_body not in SUPPORTED_BODIES:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unsupported body: {body}")
    if condition not in MOTION_CONDITIONS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unsupported condition: {condition}")
    result = analyze_retrograde_numbers(
        body=normalized_body, condition=condition, number_role=number_role, start_date=start_date  # type: ignore[arg-type]
    )
    return MarkSixAstroResearch.model_validate(result)


@router.post("/worldlines", response_model=MarkSixWorldlineResponse)
def create_marksix_worldlines(request: MarkSixWorldlineRequest) -> MarkSixWorldlineResponse:
    status = database_status()
    number_weights = None
    astro_context = None
    if request.generation_mode == "astro_association_entertainment_v1":
        analysis = analyze_retrograde_numbers(body=request.astro_body, condition=request.astro_condition)
        number_weights = {row["number"]: row["lift"] or 1.0 for row in analysis["numbers"]}
        astro_context = {
            "body": request.astro_body, "condition": request.astro_condition,
            "condition_draws": analysis["condition_draws"], "baseline_draws": analysis["baseline_draws"],
            "rule_era": analysis["rule_era"],
            "note": "Historical association weights for entertainment only; no predictive advantage is established.",
        }
    worldlines = generate_worldlines(
        horizon_draws=request.horizon_draws,
        worldline_count=request.worldline_count,
        seed=request.seed,
        language=request.language,
        generation_mode=request.generation_mode,
        number_weights=number_weights,
        astro_context=astro_context,
    )
    return MarkSixWorldlineResponse(
        worldlines=worldlines,
        historical_draw_count=status["total_draws"],
        coverage_start=status["coverage_start"],
        coverage_end=status["coverage_end"],
        method_note=(
            "Uniform random demonstration only. Historical frequencies are descriptive and do not "
            "change the probability of a future valid combination. Future dates are illustrative."
        ),
    )

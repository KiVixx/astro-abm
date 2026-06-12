from __future__ import annotations

from fastapi import APIRouter, HTTPException

from astro_abm_api.models.report import ScenarioReport
from astro_abm_api.models.scenario import ScenarioCreateRequest, ScenarioSummary
from astro_abm_api.services.agents import resolve_agents
from astro_abm_api.services.asset_registry import normalize_asset_ids
from astro_abm_api.services.daily_context import build_daily_context
from astro_abm_api.services.scenario_store import ScenarioNotFoundError, ScenarioStore
from astro_abm_api.services.simulation_engine import generate_scenario_report


router = APIRouter()


@router.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return ScenarioStore().list_summaries()


@router.get("/scenarios/{scenario_id}", response_model=ScenarioReport)
def get_scenario(scenario_id: str) -> ScenarioReport:
    try:
        return ScenarioStore().load(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scenario not found") from exc


@router.post("/scenarios", response_model=ScenarioReport)
def create_scenario(request: ScenarioCreateRequest) -> ScenarioReport:
    agents, unknown = resolve_agents(request.agent_ids)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown agent_id: {', '.join(unknown)}",
        )
    request = request.model_copy(update={"assets": normalize_asset_ids(request.assets)})
    daily_context = build_daily_context(request)
    report = generate_scenario_report(request, agents, daily_context)
    return ScenarioStore().save(report)

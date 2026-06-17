from __future__ import annotations

from fastapi import APIRouter, HTTPException

from astro_abm_api.models.report import ScenarioLlmChunkResponse, ScenarioReport
from astro_abm_api.models.scenario import (
    ScenarioCreateRequest,
    ScenarioLlmChunkRequest,
    ScenarioSummary,
)
from astro_abm_api.services.agents import resolve_agents
from astro_abm_api.services.asset_registry import normalize_asset_ids
from astro_abm_api.services.daily_context import build_daily_context
from astro_abm_api.services.scenario_store import ScenarioNotFoundError, ScenarioStore
from astro_abm_api.services.llm_client import (
    generate_llm_scenario_report_chunk,
    merge_llm_report_chunk,
)
from astro_abm_api.services.simulation_engine import generate_scenario_report, render_markdown


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


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str) -> dict[str, object]:
    try:
        ScenarioStore().delete(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scenario not found") from exc
    return {"scenario_id": scenario_id, "deleted": True}


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


@router.post("/scenarios/{scenario_id}/llm-chunks", response_model=ScenarioLlmChunkResponse)
def generate_scenario_llm_chunk(
    scenario_id: str,
    request: ScenarioLlmChunkRequest,
) -> ScenarioLlmChunkResponse:
    store = ScenarioStore()
    try:
        report = store.load(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scenario not found") from exc

    if request.chunk_start_date < report.start_date or request.chunk_end_date > report.end_date:
        raise HTTPException(
            status_code=400,
            detail="chunk date range must stay inside scenario date range",
        )

    chunk_report = generate_llm_scenario_report_chunk(request, report)
    merged_llm_report = merge_llm_report_chunk(report.llm_report, chunk_report)
    provenance = dict(report.provenance)
    provenance["llm"] = {
        "provider": request.llm_provider,
        "base_url": request.llm_base_url,
        "model": request.llm_model,
        "credential_status": merged_llm_report.provenance.credential_status,
        "network_call_performed": merged_llm_report.provenance.network_call_performed,
        "chunked_generation": True,
        "last_chunk_index": request.chunk_index,
        "total_chunks": request.total_chunks,
    }
    updated_report = report.model_copy(
        update={
            "llm_report": merged_llm_report,
            "provenance": provenance,
        }
    )
    updated_report = updated_report.model_copy(
        update={"markdown_report": render_markdown(updated_report)}
    )
    saved_report = store.save(updated_report)
    return ScenarioLlmChunkResponse(
        scenario_id=scenario_id,
        chunk_index=request.chunk_index,
        total_chunks=request.total_chunks,
        chunk_start_date=request.chunk_start_date,
        chunk_end_date=request.chunk_end_date,
        llm_status=chunk_report.status,
        completed=chunk_report.status == "completed" and request.chunk_index == request.total_chunks,
        report=saved_report,
    )

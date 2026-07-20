from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from astro_abm_api.models.report import (
    ScenarioLlmChunkResponse,
    ScenarioReport,
    ScenarioWorldlineChunkResponse,
    ScenarioWorldlineRegenerateFromRequest,
    ScenarioWorldlineRegenerateFromResponse,
)
from astro_abm_api.models.scenario import (
    ScenarioCreateRequest,
    ScenarioLlmChunkRequest,
    ScenarioWorldlineChunkRequest,
    ScenarioSummary,
)
from astro_abm_api.services.agents import resolve_agents
from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.auth_session import require_csrf
from astro_abm_api.services.asset_registry import normalize_asset_ids
from astro_abm_api.services.daily_context import build_daily_context
from astro_abm_api.services.scenario_store import (
    ScenarioNotFoundError,
    ScenarioStore,
    ScenarioUnreadableError,
)
from astro_abm_api.services.scenario_access import (
    ScenarioActor,
    actor_for_create,
    actor_for_request,
    can_mutate,
    can_read,
    is_owner,
    save_new_ownership,
)
from astro_abm_api.services.usage_limits import (
    enforce_generation_rate,
    enforce_scenario_create_network_limits,
    enforce_scenario_create_limits,
)
from astro_abm_api.services.llm_client import (
    generate_llm_scenario_report_chunk,
    merge_llm_report_chunk,
)
from astro_abm_api.services.llm_preset_store import (
    LlmPresetNotFoundError,
    LlmPresetStore,
)
from astro_abm_api.services.simulation_engine import generate_scenario_report, render_markdown
from astro_abm_api.services.worldline_llm_generator import generate_worldline_chunk
from astro_abm_api.services.worldline_regeneration import regenerate_worldline_from_chunk


router = APIRouter()


@router.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios(request: Request) -> list[ScenarioSummary]:
    store = ScenarioStore()
    auth_store = AuthStore()
    actor = actor_for_request(request)
    visible: list[ScenarioSummary] = []
    for summary in store.list_summaries():
        report = _load_scenario(store, summary.scenario_id)
        ownership = auth_store.get_scenario_ownership(summary.scenario_id)
        if not can_read(actor, report, ownership):
            continue
        owned = is_owner(actor, ownership)
        visible.append(
            summary.model_copy(
                update={
                    "is_owner": owned,
                    "can_edit": owned,
                    "can_delete": owned,
                    "can_regenerate": owned,
                }
            )
        )
    return visible


@router.get("/scenarios/{scenario_id}", response_model=ScenarioReport)
def get_scenario(
    scenario_id: str,
    request: Request,
    include_markdown: bool = True,
) -> ScenarioReport:
    report = _load_scenario(ScenarioStore(), scenario_id)
    _require_read_access(request, report)
    if include_markdown:
        return report
    return report.model_copy(update={"markdown_report": ""})


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str, request: Request) -> dict[str, object]:
    store = ScenarioStore()
    report = _load_scenario(store, scenario_id)
    _require_owner(request, report)
    try:
        store.delete(scenario_id)
        AuthStore().delete_scenario_ownership(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scenario not found") from exc
    return {"scenario_id": scenario_id, "deleted": True}


@router.post("/scenarios", response_model=ScenarioReport)
def create_scenario(
    payload: ScenarioCreateRequest,
    request: Request,
    response: Response,
) -> ScenarioReport:
    payload, _ = _resolve_request_preset(payload)
    auth_store = AuthStore()
    enforce_scenario_create_network_limits(request, auth_store)
    actor = actor_for_create(request, response)
    if actor.user is not None:
        require_csrf(request)
    if actor.user is None and payload.visibility != "public":
        payload = payload.model_copy(update={"visibility": "public"})
    enforce_scenario_create_limits(actor, auth_store)
    agents, unknown = resolve_agents(payload.agent_ids)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown agent_id: {', '.join(unknown)}",
        )
    payload = payload.model_copy(update={"assets": normalize_asset_ids(payload.assets)})
    daily_context = build_daily_context(payload)
    report = generate_scenario_report(payload, agents, daily_context)
    saved = ScenarioStore().save(report)
    save_new_ownership(report=saved, actor=actor, auth_store=auth_store)
    return saved


@router.post("/scenarios/{scenario_id}/llm-chunks", response_model=ScenarioLlmChunkResponse)
def generate_scenario_llm_chunk(
    scenario_id: str,
    payload: ScenarioLlmChunkRequest,
    request: Request,
) -> ScenarioLlmChunkResponse:
    payload, _ = _resolve_request_preset(payload)
    store = ScenarioStore()
    report = _load_scenario(store, scenario_id)
    actor = _require_owner(request, report)
    enforce_generation_rate(actor, AuthStore(), request)

    if payload.chunk_start_date < report.start_date or payload.chunk_end_date > report.end_date:
        raise HTTPException(
            status_code=400,
            detail="chunk date range must stay inside scenario date range",
        )

    chunk_report = generate_llm_scenario_report_chunk(payload, report)
    merged_llm_report = merge_llm_report_chunk(report.llm_report, chunk_report)
    provenance = dict(report.provenance)
    provenance["llm"] = {
        "provider": payload.llm_provider,
        "base_url": payload.llm_base_url,
        "model": payload.llm_model,
        "credential_status": merged_llm_report.provenance.credential_status,
        "network_call_performed": merged_llm_report.provenance.network_call_performed,
        "chunked_generation": True,
        "last_chunk_index": payload.chunk_index,
        "total_chunks": payload.total_chunks,
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
        chunk_index=payload.chunk_index,
        total_chunks=payload.total_chunks,
        chunk_start_date=payload.chunk_start_date,
        chunk_end_date=payload.chunk_end_date,
        llm_status=chunk_report.status,
        completed=chunk_report.status == "completed" and payload.chunk_index == payload.total_chunks,
        report=saved_report,
    )


@router.post(
    "/scenarios/{scenario_id}/worldline-chunks",
    response_model=ScenarioWorldlineChunkResponse,
)
def generate_scenario_worldline_chunk(
    scenario_id: str,
    payload: ScenarioWorldlineChunkRequest,
    request: Request,
) -> ScenarioWorldlineChunkResponse:
    payload, preset_record = _resolve_request_preset(payload)
    store = ScenarioStore()
    report = _load_scenario(store, scenario_id)
    actor = _require_owner(request, report)
    enforce_generation_rate(actor, AuthStore(), request)

    if payload.chunk_start_date < report.start_date or payload.chunk_end_date > report.end_date:
        raise HTTPException(
            status_code=400,
            detail="chunk date range must stay inside scenario date range",
        )

    worldline_simulation = generate_worldline_chunk(payload, report)
    if preset_record and worldline_simulation.generation_config:
        worldline_simulation = worldline_simulation.model_copy(
            update={
                "generation_config": worldline_simulation.generation_config.model_copy(
                    update={
                        "preset_id": payload.llm_preset_id,
                        "preset_name": preset_record.get("name"),
                        "credential_status": (
                            "stored_local" if preset_record.get("api_key") else "env_required"
                        ),
                    }
                )
            }
        )
    provenance = dict(report.provenance)
    provenance["worldline"] = {
        "provider": payload.llm_provider,
        "base_url": payload.llm_base_url,
        "model": payload.llm_model,
        "credential_status": worldline_simulation.provenance.get("credential_status"),
        "network_call_performed": worldline_simulation.provenance.get("network_call_performed"),
        "chunked_generation": True,
        "last_chunk_index": payload.chunk_index,
        "total_chunks": payload.total_chunks,
        "generation_mode": worldline_simulation.provenance.get("generation_mode"),
        "failed_chunk_count": worldline_simulation.provenance.get("failed_chunk_count"),
    }
    updated_report = report.model_copy(
        update={
            "worldline_simulation": worldline_simulation,
            "provenance": provenance,
        }
    )
    updated_report = updated_report.model_copy(
        update={"markdown_report": render_markdown(updated_report)}
    )
    saved_report = store.save(updated_report)
    return ScenarioWorldlineChunkResponse(
        scenario_id=scenario_id,
        chunk_index=payload.chunk_index,
        total_chunks=payload.total_chunks,
        chunk_start_date=payload.chunk_start_date,
        chunk_end_date=payload.chunk_end_date,
        worldline_status=worldline_simulation.status,
        completed=(
            worldline_simulation.status == "completed"
            and payload.chunk_index == payload.total_chunks
        ),
        consecutive_failed_chunk_count=int(
            worldline_simulation.provenance.get("consecutive_failed_chunk_count", 0)
        ),
        generation_halted=bool(
            worldline_simulation.provenance.get("generation_halted", False)
        ),
        halt_reason=worldline_simulation.provenance.get("halt_reason"),
        report=saved_report,
    )


@router.post(
    "/scenarios/{scenario_id}/worldline/regenerate-from",
    response_model=ScenarioWorldlineRegenerateFromResponse,
)
def regenerate_scenario_worldline_from_chunk(
    scenario_id: str,
    payload: ScenarioWorldlineRegenerateFromRequest,
    request: Request,
) -> ScenarioWorldlineRegenerateFromResponse:
    store = ScenarioStore()
    report = _load_scenario(store, scenario_id)
    actor = _require_owner(request, report)
    enforce_generation_rate(actor, AuthStore(), request)

    try:
        result = regenerate_worldline_from_chunk(
            report,
            start_chunk_index=payload.start_chunk_index,
            note=payload.note,
            regeneration_id=payload.regeneration_id,
            progressive=payload.progressive,
            preset_id=payload.preset_id,
            llm_overrides=payload.llm_overrides,
        )
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated_report = result.report.model_copy(
        update={"markdown_report": render_markdown(result.report)}
    )
    saved_report = store.save(updated_report)
    return ScenarioWorldlineRegenerateFromResponse(
        scenario_id=scenario_id,
        start_chunk_index=payload.start_chunk_index,
        rebuilt_chunk_count=result.rebuilt_chunk_count,
        continuity_status=saved_report.worldline_simulation.continuity_status
        if saved_report.worldline_simulation
        else "legacy_unknown",
        regeneration_status=result.regeneration_status,
        llm_completed_chunk_count=result.llm_completed_chunk_count,
        fallback_chunk_count=result.fallback_chunk_count,
        skipped_chunk_count=result.skipped_chunk_count,
        report=saved_report,
    )


def _load_scenario(store: ScenarioStore, scenario_id: str) -> ScenarioReport:
    try:
        return store.load(scenario_id)
    except ScenarioUnreadableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scenario not found") from exc


def _require_read_access(request: Request, report: ScenarioReport) -> None:
    actor = actor_for_request(request)
    ownership = AuthStore().get_scenario_ownership(report.scenario_id)
    if not can_read(actor, report, ownership):
        raise HTTPException(status_code=404, detail="scenario not found")


def _require_owner(request: Request, report: ScenarioReport) -> ScenarioActor:
    actor = actor_for_request(request)
    ownership = AuthStore().get_scenario_ownership(report.scenario_id)
    if not can_mutate(actor, ownership):
        raise HTTPException(status_code=404, detail="scenario not found")
    if actor.user is not None:
        require_csrf(request)
    return actor


def _resolve_request_preset(request):
    preset_id = getattr(request, "llm_preset_id", None)
    if not preset_id:
        return request, None
    try:
        record = LlmPresetStore().get_record(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc
    updates = {
        "llm_provider": record.get("provider", "openai_compatible"),
        "llm_real_enabled": (
            request.llm_real_enabled
            if request.llm_real_enabled is not None
            else bool(record.get("real_enabled", True))
        ),
        "llm_base_url": request.llm_base_url or record.get("base_url"),
        "llm_model": request.llm_model or record.get("model"),
        "llm_api_key": request.llm_api_key or record.get("api_key"),
        "llm_user_prompt": request.llm_user_prompt or record.get("custom_user_prompt"),
        "llm_timeout_seconds": request.llm_timeout_seconds or record.get("timeout_seconds"),
        "llm_max_output_tokens": (
            request.llm_max_output_tokens or record.get("max_output_tokens")
        ),
        "llm_call_delay_seconds": (
            request.llm_call_delay_seconds
            if request.llm_call_delay_seconds is not None
            else record.get("call_delay_seconds")
        ),
    }
    return request.model_copy(update=updates), record

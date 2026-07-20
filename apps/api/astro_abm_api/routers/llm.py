from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request

from astro_abm_api.models.llm import LLMTestRequest, LLMTestResponse
from astro_abm_api.models.llm_preset import (
    LlmPresetSaveRequest,
    LlmPresetSummary,
    LlmPresetTestResponse,
)
from astro_abm_api.services.llm_client import test_llm_connection
from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.client_identity import client_rate_key
from astro_abm_api.services.generation_capacity import generation_capacity
from astro_abm_api.services.scenario_access import ScenarioActor
from astro_abm_api.services.usage_limits import enforce_generation_rate
from astro_abm_api.services.llm_preset_store import (
    LlmPresetNotFoundError,
    LlmPresetStore,
)


router = APIRouter()


def _preset_management_enabled() -> bool:
    production = os.getenv("ASTRO_ABM_ENV", "development").strip().lower() == "production"
    configured = os.getenv("ASTRO_ABM_ALLOW_REMOTE_PRESET_MANAGEMENT")
    if configured is None:
        return not production
    return configured.strip().lower() in {"1", "true", "yes", "on"}


def _require_preset_management() -> None:
    if not _preset_management_enabled():
        raise HTTPException(status_code=403, detail="remote LLM preset management is disabled")


@router.post("/llm/test", response_model=LLMTestResponse)
def test_llm(payload: LLMTestRequest, request: Request) -> LLMTestResponse:
    actor = ScenarioActor("network", client_rate_key(request), None)
    store = AuthStore()
    enforce_generation_rate(actor, store, request)
    with generation_capacity(actor, store):
        return test_llm_connection(payload)


@router.get("/llm/presets", response_model=list[LlmPresetSummary])
def list_llm_presets() -> list[LlmPresetSummary]:
    if not _preset_management_enabled():
        return []
    return LlmPresetStore().list()


@router.post("/llm/presets", response_model=LlmPresetSummary)
def create_llm_preset(request: LlmPresetSaveRequest) -> LlmPresetSummary:
    _require_preset_management()
    return LlmPresetStore().create(request)


@router.put("/llm/presets/{preset_id}", response_model=LlmPresetSummary)
def update_llm_preset(
    preset_id: str, request: LlmPresetSaveRequest
) -> LlmPresetSummary:
    _require_preset_management()
    try:
        return LlmPresetStore().update(preset_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc


@router.delete("/llm/presets/{preset_id}")
def delete_llm_preset(preset_id: str) -> dict[str, object]:
    _require_preset_management()
    try:
        LlmPresetStore().delete(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc
    return {"preset_id": preset_id, "deleted": True}


@router.post("/llm/presets/{preset_id}/test", response_model=LlmPresetTestResponse)
def test_llm_preset(preset_id: str, request: Request) -> LlmPresetTestResponse:
    _require_preset_management()
    try:
        record = LlmPresetStore().get_record(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc
    actor = ScenarioActor("network", client_rate_key(request), None)
    store = AuthStore()
    enforce_generation_rate(actor, store, request)
    with generation_capacity(actor, store):
        response = test_llm_connection(
            LLMTestRequest(
                provider=record.get("provider", "openai_compatible"),
                real_enabled=record.get("real_enabled"),
                base_url=record.get("base_url"),
                model=record.get("model"),
                api_key=record.get("api_key"),
                timeout_seconds=record.get("timeout_seconds"),
                max_output_tokens=record.get("max_output_tokens"),
            )
        )
    return LlmPresetTestResponse(
        preset_id=preset_id,
        reachable=response.reachable,
        dry_run=response.dry_run,
        status=response.status,
        message=response.message,
        provider=response.provider,
        model=response.model,
        credential_status=("stored_local" if record.get("api_key") else "not_configured"),
    )

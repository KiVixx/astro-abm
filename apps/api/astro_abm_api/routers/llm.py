from __future__ import annotations

from fastapi import APIRouter, HTTPException

from astro_abm_api.models.llm import LLMTestRequest, LLMTestResponse
from astro_abm_api.models.llm_preset import (
    LlmPresetSaveRequest,
    LlmPresetSummary,
    LlmPresetTestResponse,
)
from astro_abm_api.services.llm_client import test_llm_connection
from astro_abm_api.services.llm_preset_store import (
    LlmPresetNotFoundError,
    LlmPresetStore,
)


router = APIRouter()


@router.post("/llm/test", response_model=LLMTestResponse)
def test_llm(request: LLMTestRequest) -> LLMTestResponse:
    return test_llm_connection(request)


@router.get("/llm/presets", response_model=list[LlmPresetSummary])
def list_llm_presets() -> list[LlmPresetSummary]:
    return LlmPresetStore().list()


@router.post("/llm/presets", response_model=LlmPresetSummary)
def create_llm_preset(request: LlmPresetSaveRequest) -> LlmPresetSummary:
    return LlmPresetStore().create(request)


@router.put("/llm/presets/{preset_id}", response_model=LlmPresetSummary)
def update_llm_preset(
    preset_id: str, request: LlmPresetSaveRequest
) -> LlmPresetSummary:
    try:
        return LlmPresetStore().update(preset_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc


@router.delete("/llm/presets/{preset_id}")
def delete_llm_preset(preset_id: str) -> dict[str, object]:
    try:
        LlmPresetStore().delete(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc
    return {"preset_id": preset_id, "deleted": True}


@router.post("/llm/presets/{preset_id}/test", response_model=LlmPresetTestResponse)
def test_llm_preset(preset_id: str) -> LlmPresetTestResponse:
    try:
        record = LlmPresetStore().get_record(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmPresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LLM preset not found") from exc
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

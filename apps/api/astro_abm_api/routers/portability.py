from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response

from astro_abm_api.models.portability import ScenarioExportEnvelope, ScenarioImportRequest
from astro_abm_api.models.report import ScenarioReport
from astro_abm_api.services.auth_session import require_csrf
from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.scenario_access import (
    actor_for_create,
    actor_for_request,
    can_read,
    save_new_ownership,
)
from astro_abm_api.services.scenario_portability import export_scenario, validate_export
from astro_abm_api.services.scenario_store import (
    ScenarioNotFoundError,
    ScenarioStore,
    ScenarioUnreadableError,
)
from astro_abm_api.services.simulation_engine import create_scenario_id, render_markdown
from astro_abm_api.services.usage_limits import (
    enforce_scenario_create_limits,
    enforce_scenario_create_network_limits,
)


router = APIRouter(tags=["scenario portability"])


@router.get("/scenarios/{scenario_id}/export", response_model=ScenarioExportEnvelope)
def export_worldline(scenario_id: str, request: Request) -> ScenarioExportEnvelope:
    store = ScenarioStore()
    try:
        report = store.load(scenario_id)
    except ScenarioNotFoundError as error:
        raise HTTPException(status_code=404, detail="scenario not found") from error
    except (ScenarioUnreadableError, ValueError) as error:
        raise HTTPException(status_code=422, detail="scenario export unavailable") from error
    actor = actor_for_request(request)
    ownership = AuthStore().get_scenario_ownership(scenario_id)
    if not can_read(actor, report, ownership):
        raise HTTPException(status_code=404, detail="scenario not found")
    return export_scenario(report)


@router.post("/scenarios/import", response_model=ScenarioReport)
def import_worldline(
    payload: ScenarioImportRequest,
    request: Request,
    response: Response,
) -> ScenarioReport:
    try:
        source = validate_export(payload.envelope)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    auth_store = AuthStore()
    enforce_scenario_create_network_limits(request, auth_store)
    actor = actor_for_create(request, response)
    if actor.user is not None:
        require_csrf(request)
    enforce_scenario_create_limits(actor, auth_store)
    visibility = payload.visibility or source.visibility
    if actor.user is None:
        visibility = "public"
    imported_at = datetime.now(UTC)
    provenance = dict(source.provenance)
    provenance["import"] = {
        "schema_version": payload.envelope.schema_version,
        "source_content_hash": payload.envelope.content_hash,
        "imported_at": imported_at.isoformat(),
    }
    imported = source.model_copy(
        update={
            "scenario_id": create_scenario_id(source.title, imported_at),
            "created_at": imported_at,
            "visibility": visibility,
            "provenance": provenance,
        }
    )
    imported = imported.model_copy(update={"markdown_report": render_markdown(imported)})
    saved = ScenarioStore().save(imported)
    save_new_ownership(report=saved, actor=actor, auth_store=auth_store)
    return saved

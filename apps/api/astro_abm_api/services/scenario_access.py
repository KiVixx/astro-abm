from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request, Response

from astro_abm_api.models.auth import CurrentUser
from astro_abm_api.models.report import ScenarioReport
from astro_abm_api.services.auth_session import current_user, ensure_guest, guest_id
from astro_abm_api.services.auth_store import AuthStore, ScenarioOwnership


@dataclass(frozen=True)
class ScenarioActor:
    owner_type: str | None
    owner_id: str | None
    user: CurrentUser | None


def actor_for_request(request: Request) -> ScenarioActor:
    user = current_user(request)
    if user:
        return ScenarioActor("user", user.user_id, user)
    anonymous_id = guest_id(request)
    return ScenarioActor("guest" if anonymous_id else None, anonymous_id, None)


def actor_for_create(request: Request, response: Response) -> ScenarioActor:
    user = current_user(request)
    if user:
        return ScenarioActor("user", user.user_id, user)
    anonymous_id = ensure_guest(request, response)
    return ScenarioActor("guest", anonymous_id, None)


def is_owner(actor: ScenarioActor, ownership: ScenarioOwnership | None) -> bool:
    return bool(
        ownership
        and actor.owner_type == ownership.owner_type
        and actor.owner_id == ownership.owner_id
    )


def can_read(
    actor: ScenarioActor,
    report: ScenarioReport,
    ownership: ScenarioOwnership | None,
) -> bool:
    visibility = ownership.visibility if ownership else report.visibility
    if visibility == "public":
        return True
    return is_owner(actor, ownership)


def can_mutate(actor: ScenarioActor, ownership: ScenarioOwnership | None) -> bool:
    return is_owner(actor, ownership)


def save_new_ownership(
    *,
    report: ScenarioReport,
    actor: ScenarioActor,
    auth_store: AuthStore,
) -> None:
    if actor.owner_type is None or actor.owner_id is None:
        raise RuntimeError("scenario owner is required")
    auth_store.set_scenario_ownership(
        scenario_id=report.scenario_id,
        owner_type=actor.owner_type,
        owner_id=actor.owner_id,
        visibility=report.visibility,
    )

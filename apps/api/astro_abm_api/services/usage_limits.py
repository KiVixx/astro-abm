from __future__ import annotations

import os

from fastapi import HTTPException

from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.scenario_access import ScenarioActor


def _bounded_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def enforce_scenario_create_limits(actor: ScenarioActor, store: AuthStore) -> None:
    if not actor.owner_type or not actor.owner_id:
        raise HTTPException(status_code=403, detail="scenario owner is unavailable")
    quota = _bounded_env(
        "ASTRO_ABM_USER_SCENARIO_QUOTA" if actor.user else "ASTRO_ABM_GUEST_SCENARIO_QUOTA",
        200 if actor.user else 20,
        1,
        10000,
    )
    if store.count_owned_scenarios(owner_type=actor.owner_type, owner_id=actor.owner_id) >= quota:
        raise HTTPException(status_code=429, detail="worldline storage quota reached")
    _enforce_rate(actor, store, "scenario_create", "ASTRO_ABM_CREATE_RATE_PER_HOUR", 60)


def enforce_generation_rate(actor: ScenarioActor, store: AuthStore) -> None:
    _enforce_rate(actor, store, "llm_generation", "ASTRO_ABM_LLM_RATE_PER_HOUR", 240)


def _enforce_rate(
    actor: ScenarioActor,
    store: AuthStore,
    operation: str,
    env_name: str,
    default: int,
) -> None:
    if not actor.owner_type or not actor.owner_id:
        raise HTTPException(status_code=403, detail="scenario owner is unavailable")
    allowed = store.record_operation_if_allowed(
        actor_type=actor.owner_type,
        actor_id=actor.owner_id,
        operation=operation,
        limit=_bounded_env(env_name, default, 1, 100000),
        window_seconds=3600,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="operation rate limit reached; retry later")

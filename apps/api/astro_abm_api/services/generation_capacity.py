from __future__ import annotations

import os
from contextlib import contextmanager

from fastapi import HTTPException

from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.scenario_access import ScenarioActor


@contextmanager
def generation_capacity(actor: ScenarioActor, store: AuthStore):  # type: ignore[no-untyped-def]
    if not actor.owner_type or not actor.owner_id:
        raise HTTPException(status_code=403, detail="generation owner is unavailable")
    lease_id = store.try_acquire_generation_lease(
        actor_type=actor.owner_type,
        actor_id=actor.owner_id,
        global_limit=_env_int("ASTRO_ABM_GENERATION_GLOBAL_CONCURRENCY", 4, 1, 100),
        actor_limit=_env_int("ASTRO_ABM_GENERATION_OWNER_CONCURRENCY", 1, 1, 20),
        lease_seconds=_env_int("ASTRO_ABM_GENERATION_LEASE_SECONDS", 1800, 30, 86400),
    )
    if lease_id is None:
        raise HTTPException(
            status_code=503,
            detail="generation capacity busy; retry later",
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        store.release_generation_lease(lease_id)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))

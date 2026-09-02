from __future__ import annotations

import os

from fastapi import HTTPException, Request

from astro_abm_api.models.scenario import ScenarioCreateRequest
from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.client_identity import client_rate_key
from astro_abm_api.services.scenario_access import ScenarioActor


def _bounded_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def registration_enabled() -> bool:
    return os.getenv("ASTRO_ABM_REGISTRATION_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def global_registration_limit_per_hour() -> int:
    return _bounded_env(
        "ASTRO_ABM_GLOBAL_REGISTRATION_RATE_PER_HOUR",
        40,
        1,
        10000,
    )


def enforce_scenario_create_limits(
    actor: ScenarioActor,
    store: AuthStore,
) -> None:
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


def enforce_scenario_create_network_limits(request: Request, store: AuthStore) -> None:
    _enforce_ip_rate(
        request,
        store,
        operation="scenario_create_hour",
        env_name="ASTRO_ABM_IP_CREATE_RATE_PER_HOUR",
        default=12,
        window_seconds=3600,
    )
    _enforce_ip_rate(
        request,
        store,
        operation="scenario_create_day",
        env_name="ASTRO_ABM_IP_CREATE_RATE_PER_DAY",
        default=40,
        window_seconds=86400,
    )


def enforce_scenario_complexity(payload: ScenarioCreateRequest) -> None:
    horizon_days = (payload.end_date - payload.start_date).days + 1
    maximum_days = _bounded_env("ASTRO_ABM_SCENARIO_MAX_DAYS", 366, 1, 3660)
    if horizon_days > maximum_days:
        raise HTTPException(
            status_code=422,
            detail=f"scenario date range exceeds maximum of {maximum_days} days",
        )


def enforce_generation_rate(actor: ScenarioActor, store: AuthStore, request: Request) -> None:
    _enforce_rate(actor, store, "llm_generation", "ASTRO_ABM_LLM_RATE_PER_HOUR", 240)
    _enforce_ip_rate(
        request,
        store,
        operation="llm_generation_hour",
        env_name="ASTRO_ABM_IP_LLM_RATE_PER_HOUR",
        default=120,
        window_seconds=3600,
    )


def enforce_auth_rate(request: Request, store: AuthStore, operation: str) -> None:
    defaults = {
        "register": ("ASTRO_ABM_IP_REGISTER_RATE_PER_HOUR", 5, 3600),
        "login": ("ASTRO_ABM_IP_LOGIN_RATE_PER_15_MINUTES", 20, 900),
    }
    env_name, default, window_seconds = defaults[operation]
    _enforce_ip_rate(
        request,
        store,
        operation=f"auth_{operation}",
        env_name=env_name,
        default=default,
        window_seconds=window_seconds,
    )


def enforce_market_series_operation(
    request: Request,
    store: AuthStore,
    *,
    user_id: str,
    operation: str,
) -> None:
    defaults = {
        "register": (
            "ASTRO_ABM_MARKET_SERIES_REGISTER_RATE_PER_HOUR",
            "ASTRO_ABM_IP_MARKET_SERIES_REGISTER_RATE_PER_HOUR",
            10,
        ),
        "validate": (
            "ASTRO_ABM_MARKET_SERIES_REFRESH_RATE_PER_HOUR",
            "ASTRO_ABM_IP_MARKET_SERIES_REFRESH_RATE_PER_HOUR",
            12,
        ),
        "refresh": (
            "ASTRO_ABM_MARKET_SERIES_REFRESH_RATE_PER_HOUR",
            "ASTRO_ABM_IP_MARKET_SERIES_REFRESH_RATE_PER_HOUR",
            12,
        ),
    }
    env_name, ip_env_name, default = defaults[operation]
    actor = ScenarioActor(owner_type="user", owner_id=user_id, user=None)
    _enforce_rate(actor, store, f"market_series_{operation}", env_name, default)
    _enforce_ip_rate(
        request,
        store,
        operation=f"market_series_{operation}_hour",
        env_name=ip_env_name,
        default=max(default, 20),
        window_seconds=3600,
    )


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
        raise HTTPException(
            status_code=429,
            detail="operation rate limit reached; retry later",
            headers={"Retry-After": "3600"},
        )


def _enforce_ip_rate(
    request: Request,
    store: AuthStore,
    *,
    operation: str,
    env_name: str,
    default: int,
    window_seconds: int,
) -> None:
    allowed = store.record_operation_if_allowed(
        actor_type="network",
        actor_id=client_rate_key(request),
        operation=operation,
        limit=_bounded_env(env_name, default, 1, 100000),
        window_seconds=window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="network rate limit reached; retry later",
            headers={"Retry-After": str(window_seconds)},
        )

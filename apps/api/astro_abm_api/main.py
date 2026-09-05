# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from astro_abm_api.middleware.request_limits import RequestBodyLimitMiddleware
from astro_abm_api.routers import (
    agents,
    assets,
    auth,
    health,
    llm,
    market_series,
    marksix,
    portability,
    scenarios,
)
from astro_abm_api.services.scenario_store import ScenarioCapacityError


LOCAL_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def _allowed_origins() -> tuple[list[str], str | None]:
    configured = [
        origin.strip().rstrip("/")
        for origin in os.getenv("ASTRO_ABM_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    production = os.getenv("ASTRO_ABM_ENV", "development").strip().lower() == "production"
    return configured, None if production else LOCAL_CORS_ORIGIN_REGEX


def create_app() -> FastAPI:
    allowed_origins, allowed_origin_regex = _allowed_origins()
    app = FastAPI(
        title="Astro ABM API",
        description="Local-first scenario simulation API for Astro ABM.",
        version="0.1.0",
    )
    app.add_middleware(RequestBodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    @app.exception_handler(ScenarioCapacityError)
    async def scenario_capacity_error(_request, error: ScenarioCapacityError):  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=507,
            content={"detail": "scenario storage capacity reached", "category": error.category},
            headers={"Retry-After": "3600"},
        )
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(assets.router)
    app.include_router(market_series.router)
    app.include_router(marksix.router)
    app.include_router(auth.router)
    app.include_router(portability.router)
    app.include_router(scenarios.router)
    app.include_router(llm.router)
    return app


app = create_app()

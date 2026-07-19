# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from astro_abm_api.routers import agents, assets, health, llm, scenarios


LOCAL_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Astro ABM API",
        description="Local-first scenario simulation API for Astro ABM.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCAL_CORS_ORIGIN_REGEX,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(assets.router)
    app.include_router(scenarios.router)
    app.include_router(llm.router)
    return app


app = create_app()

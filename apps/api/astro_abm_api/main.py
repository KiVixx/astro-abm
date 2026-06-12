from __future__ import annotations

from fastapi import FastAPI

from astro_abm_api.routers import agents, assets, health, llm, scenarios


def create_app() -> FastAPI:
    app = FastAPI(
        title="Astro ABM API",
        description="Local-first scenario simulation API for Astro ABM.",
        version="0.1.0",
    )
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(assets.router)
    app.include_router(scenarios.router)
    app.include_router(llm.router)
    return app


app = create_app()

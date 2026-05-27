from __future__ import annotations

from fastapi import APIRouter

from astro_abm_api.models.agent import AgentProfile
from astro_abm_api.services.agents import list_agents


router = APIRouter()


@router.get("/agents", response_model=list[AgentProfile])
def get_agents() -> list[AgentProfile]:
    return list_agents()

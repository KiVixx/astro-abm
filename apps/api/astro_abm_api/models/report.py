from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from astro_abm_api.models.agent import AgentOutput, AgentProfile
from astro_abm_api.models.scenario import ScenarioMode, Visibility


class ScenarioReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    title: str
    description: str | None = None
    created_at: datetime
    start_date: date
    end_date: date
    assets: list[str]
    agents: list[AgentProfile]
    daily_context: dict[str, Any]
    simulation_summary: str
    agent_outputs: list[AgentOutput]
    risks: list[str]
    caveats: list[str]
    provenance: dict[str, Any]
    visibility: Visibility
    mode: ScenarioMode
    markdown_report: str
    disclaimer: str

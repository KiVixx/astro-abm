from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from astro_abm_api.models.agent import AgentOutput, AgentProfile
from astro_abm_api.models.scenario import ScenarioMode, Visibility


class DailyAstroContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    event_tags: list[str]
    intensity: str


class DailyMarketContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    stress_regime: str
    volatility_regime: str
    liquidity_regime: str


class DailyAgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_name: str
    mood: str
    risk_appetite: str
    likely_reaction: str
    attention_triggers: list[str]
    caveats: list[str]


class DailyScenarioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    day_index: int
    assets: list[str]
    astro_context: DailyAstroContext
    market_context: DailyMarketContext
    agent_states: list[DailyAgentState]
    daily_risk_themes: list[str]
    daily_summary: str
    confidence: str
    caveats: list[str]
    disclaimer: str


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
    scenario_summary: str | None = None
    agent_outputs: list[AgentOutput]
    risks: list[str]
    risk_themes: list[str] = Field(default_factory=list)
    daily_timeline: list[DailyScenarioSnapshot] = Field(default_factory=list)
    caveats: list[str]
    provenance: dict[str, Any]
    visibility: Visibility
    mode: ScenarioMode
    markdown_report: str
    disclaimer: str

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_tolerance: str = Field(min_length=1)
    time_horizon: str = Field(min_length=1)
    macro_sensitivity: str = Field(min_length=1)
    astro_narrative_sensitivity: str = Field(min_length=1)
    liquidity_sensitivity: str = Field(min_length=1)
    decision_style: str = Field(min_length=1)


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_name: str
    role: str
    behavior_summary: str
    risk_appetite: str
    likely_reaction: str
    confidence: str
    caveats: list[str]

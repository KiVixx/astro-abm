from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from astro_abm_api.models.agent import AgentOutput, AgentProfile
from astro_abm_api.models.asset import MarketSeriesProfile
from astro_abm_api.models.scenario import ReportLanguage, ScenarioMode, Visibility


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


class DailyDataCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    astro_daily: str = "unknown"
    financial_stress_daily: str = "unknown"
    market_daily: str = "unknown"
    macro_daily: str = "unknown"
    source: str = "legacy_report"
    notes: list[str] = Field(default_factory=list)


class DailyResearchSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stress_regime: str = "unknown"
    volatility_regime: str = "unknown"
    liquidity_regime: str = "unknown"
    astro_activity: str = "unknown"
    data_quality: str = "unknown"


class DailyAgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_name: str
    mood: str
    risk_appetite: str
    likely_reaction: str
    attention_triggers: list[str]
    caveats: list[str]


class DailyAssetContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    label: str
    series_type: str
    supported: bool
    market_daily: str
    data_source: str
    data_quality: str
    return_1d: float | None = None
    volatility_value: float | None = None
    volatility_regime: str = "unknown"
    stress_sentiment: str = "unknown"
    notes: list[str] = Field(default_factory=list)


class DailyScenarioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    day_index: int
    assets: list[str]
    astro_context: DailyAstroContext
    market_context: DailyMarketContext
    data_coverage: DailyDataCoverage = Field(default_factory=DailyDataCoverage)
    research_signals: DailyResearchSignals = Field(default_factory=DailyResearchSignals)
    asset_contexts: list[DailyAssetContext] = Field(default_factory=list)
    agent_states: list[DailyAgentState]
    daily_risk_themes: list[str]
    daily_summary: str
    confidence: str
    caveats: list[str]
    disclaimer: str


class AssetCoverageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    available_days: int
    missing_days: int
    future_placeholder_days: int
    coverage_status: str
    notes: list[str] = Field(default_factory=list)


class ScenarioCoverageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_days: int
    local_research_days: int
    placeholder_days: int
    future_placeholder_days: int
    mixed_context_days: int
    astro_daily_available_days: int
    financial_stress_available_days: int
    market_daily_available_days: int
    macro_daily_available_days: int
    data_sources: list[str]
    data_quality_counts: dict[str, int]
    source_counts: dict[str, int]
    asset_coverage: list[AssetCoverageSummary] = Field(default_factory=list)
    date_range_mode: str
    notes: list[str] = Field(default_factory=list)


class LlmDailyHighlight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    summary: str
    key_context: list[str] = Field(default_factory=list)
    agent_focus: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class LlmAgentInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_name: str
    interpretation: str
    risk_focus: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class LlmReportProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None = None
    base_url_status: str
    credential_status: str
    network_call_performed: bool
    prompt_template_version: str
    input_context_hash: str
    output_validation_status: str
    safety_check_status: str


class LlmScenarioReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    provider: str
    model: str | None = None
    language: ReportLanguage
    executive_summary: str
    scenario_reading: str
    daily_highlights: list[LlmDailyHighlight] = Field(default_factory=list)
    agent_interpretations: list[LlmAgentInterpretation] = Field(default_factory=list)
    risk_themes: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    disclaimer: str
    raw_text_preview: str | None = None
    provenance: LlmReportProvenance


class ScenarioReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    title: str
    description: str | None = None
    created_at: datetime
    start_date: date
    end_date: date
    assets: list[str]
    asset_profiles: list[MarketSeriesProfile] = Field(default_factory=list)
    agents: list[AgentProfile]
    daily_context: dict[str, Any]
    simulation_summary: str
    scenario_summary: str | None = None
    agent_outputs: list[AgentOutput]
    risks: list[str]
    risk_themes: list[str] = Field(default_factory=list)
    daily_timeline: list[DailyScenarioSnapshot] = Field(default_factory=list)
    coverage_summary: ScenarioCoverageSummary | None = None
    llm_report: LlmScenarioReport | None = None
    caveats: list[str]
    provenance: dict[str, Any]
    visibility: Visibility
    mode: ScenarioMode
    language: ReportLanguage | None = None
    markdown_report: str
    disclaimer: str

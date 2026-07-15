from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class LlmAssetStressIndicator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    asset: str
    sentiment_stress_support: float = Field(ge=0, le=100)
    label: str
    rationale: str
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
    asset_stress_indicators: list[LlmAssetStressIndicator] = Field(default_factory=list)
    risk_themes: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    disclaimer: str
    raw_text_preview: str | None = None
    provenance: LlmReportProvenance


class WorldlineImpactScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentiment_delta: int
    narrative_pressure_delta: int
    leverage_pressure_delta: int
    liquidity_pressure_delta: int
    volatility_pressure_delta: int
    stress_pressure_delta: int

    @field_validator("*", mode="before")
    @classmethod
    def clamp_score(cls, value: object) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = 0
        return max(-2, min(2, numeric))


class WorldlineAgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_name: str
    what_happened: str
    why_it_happened: str
    impact_on_tomorrow: str
    impact_scores: WorldlineImpactScores
    confidence: str
    caveats: list[str] = Field(default_factory=list)


class WorldlineCausalLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    description: str
    strength: str
    caveats: list[str] = Field(default_factory=list)


class WorldlineState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentiment_state: str
    narrative_pressure: float = Field(ge=0, le=1)
    leverage_pressure: float = Field(ge=0, le=1)
    liquidity_pressure: float = Field(ge=0, le=1)
    volatility_pressure: float = Field(ge=0, le=1)
    stress_pressure: float = Field(ge=0, le=1)
    regime_label: str | None = None
    notes: list[str] = Field(default_factory=list)


class WorldlineDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    day_index: int
    generation_source: str = "unknown"
    chunk_index: int | None = None
    chunk_status: str | None = None
    quality_notes: list[str] = Field(default_factory=list)
    input_context_summary: str
    world_state_before: WorldlineState
    agent_events: list[WorldlineAgentEvent]
    causal_links: list[WorldlineCausalLink]
    next_day_update: str
    world_state_after: WorldlineState
    disclaimer: str


class WorldlineGenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worldline_provider: str
    worldline_chunk_days: int
    llm_provider: str | None = None
    llm_real_enabled: bool | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float | None = None
    llm_max_output_tokens: int | None = None
    llm_call_delay_seconds: float | None = None
    report_language: str | None = None
    custom_user_prompt: str | None = None
    preset_id: str | None = None
    preset_name: str | None = None
    credential_status: str = "not_configured"


class WorldlineSimulation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    mode: str
    horizon_days: int
    days: list[WorldlineDay] = Field(default_factory=list)
    summary: str
    caveats: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    generation_config: WorldlineGenerationConfig | None = None
    continuity_status: str = "legacy_unknown"
    last_regeneration: dict[str, Any] | None = None


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
    worldline_simulation: WorldlineSimulation | None = None
    caveats: list[str]
    provenance: dict[str, Any]
    visibility: Visibility
    mode: ScenarioMode
    language: ReportLanguage | None = None
    markdown_report: str
    disclaimer: str


class ScenarioLlmChunkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    chunk_index: int
    total_chunks: int
    chunk_start_date: date
    chunk_end_date: date
    llm_status: str
    completed: bool
    report: ScenarioReport


class ScenarioWorldlineChunkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    chunk_index: int
    total_chunks: int
    chunk_start_date: date
    chunk_end_date: date
    worldline_status: str
    completed: bool
    consecutive_failed_chunk_count: int = 0
    generation_halted: bool = False
    halt_reason: str | None = None
    report: ScenarioReport


class LlmRegenerationOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    real_enabled: bool | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = Field(default=None, exclude=True, repr=False)
    timeout_seconds: float | None = Field(default=None, ge=1, le=600)
    max_output_tokens: int | None = Field(default=None, ge=512, le=32000)
    call_delay_seconds: float | None = Field(default=None, ge=0, le=120)
    custom_user_prompt: str | None = Field(default=None, max_length=4000)

    @field_validator("base_url", "model", "api_key", "custom_user_prompt")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ScenarioWorldlineRegenerateFromRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_chunk_index: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=1000)
    regeneration_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{8,80}$")
    progressive: bool = False
    preset_id: str | None = None
    llm_overrides: LlmRegenerationOverrides | None = None


class ScenarioWorldlineRegenerateFromResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    start_chunk_index: int
    rebuilt_chunk_count: int
    continuity_status: str
    regeneration_status: str
    llm_completed_chunk_count: int
    fallback_chunk_count: int
    skipped_chunk_count: int
    report: ScenarioReport

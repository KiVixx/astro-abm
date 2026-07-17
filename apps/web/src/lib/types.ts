export type Visibility = "private" | "public";
export type ScenarioMode = "daily_association_only";
export type LlmProvider = "mock" | "openai_compatible";
export type ReportLanguage = "en" | "zh-Hant";
export type WorldlineProvider = "deterministic_mock" | "llm";

export interface LlmPresetSummary {
  preset_id: string;
  name: string;
  provider: LlmProvider;
  real_enabled: boolean;
  base_url?: string | null;
  model?: string | null;
  has_api_key: boolean;
  worldline_provider: string;
  chunk_size_days: number;
  call_delay_seconds: number;
  timeout_seconds: number;
  max_output_tokens: number;
  custom_user_prompt?: string | null;
  default_language: string;
  created_at: string;
  updated_at: string;
}

export interface LlmPresetSaveRequest {
  name: string;
  provider: LlmProvider;
  real_enabled: boolean;
  base_url?: string | null;
  model?: string | null;
  api_key?: string | null;
  keep_existing_api_key?: boolean;
  worldline_provider?: string;
  chunk_size_days?: number;
  call_delay_seconds?: number;
  timeout_seconds?: number;
  max_output_tokens?: number;
  custom_user_prompt?: string | null;
  default_language?: string;
}

export interface LlmPresetTestResponse {
  preset_id: string;
  reachable: boolean;
  dry_run: boolean;
  status: string;
  message: string;
  provider: LlmProvider;
  model?: string | null;
  credential_status: string;
}

export interface LlmTestRequest {
  provider: LlmProvider;
  real_enabled?: boolean | null;
  base_url?: string | null;
  model?: string | null;
  api_key?: string | null;
  timeout_seconds?: number | null;
  max_output_tokens?: number | null;
}

export interface LlmTestResponse {
  provider: LlmProvider;
  reachable: boolean;
  dry_run: boolean;
  status: string;
  message: string;
  base_url?: string | null;
  model?: string | null;
}

export interface AgentProfile {
  agent_id: string;
  name: string;
  category: string;
  description: string;
  risk_tolerance: string;
  time_horizon: string;
  macro_sensitivity: string;
  astro_narrative_sensitivity: string;
  liquidity_sensitivity: string;
  decision_style: string;
}

export interface AgentOutput {
  agent_id: string;
  agent_name: string;
  role: string;
  behavior_summary: string;
  risk_appetite: string;
  likely_reaction: string;
  confidence: string;
  caveats: string[];
}

export interface MarketSeriesProfile {
  asset: string;
  label: string;
  series_type: string;
  aliases: string[];
  market_daily_supported: boolean;
  supported: boolean;
  notes: string[];
}

export interface DailyAstroContext {
  summary: string;
  event_tags: string[];
  intensity: string;
}

export interface DailyMarketContext {
  summary: string;
  stress_regime: string;
  volatility_regime: string;
  liquidity_regime: string;
}

export interface DailyDataCoverage {
  astro_daily: string;
  financial_stress_daily: string;
  market_daily: string;
  macro_daily: string;
  source: string;
  notes: string[];
}

export interface DailyResearchSignals {
  stress_regime: string;
  volatility_regime: string;
  liquidity_regime: string;
  astro_activity: string;
  data_quality: string;
}

export interface DailyRetrogradeBodyContext {
  body: string;
  phase: string;
  is_retrograde?: boolean | null;
  lon_speed_deg_day?: number | null;
  nearest_station_type?: string | null;
  nearest_station_ts?: string | null;
  days_to_station_nearest?: number | null;
  days_since_station?: number | null;
  days_until_station?: number | null;
  cycle_id?: string | null;
  source: string;
  data_quality: string;
  notes: string[];
}

export interface DailyRetrogradeContext {
  bodies: DailyRetrogradeBodyContext[];
  source: string;
  data_quality: string;
  notes: string[];
}

export interface DailyAgentState {
  agent_id: string;
  agent_name: string;
  mood: string;
  risk_appetite: string;
  likely_reaction: string;
  attention_triggers: string[];
  caveats: string[];
}

export interface DailyAssetContext {
  asset: string;
  label: string;
  series_type: string;
  supported: boolean;
  market_daily: string;
  data_source: string;
  data_quality: string;
  return_1d?: number | null;
  volatility_value?: number | null;
  volatility_regime: string;
  stress_sentiment: string;
  notes: string[];
}

export interface DailyScenarioSnapshot {
  date: string;
  day_index: number;
  assets: string[];
  astro_context: DailyAstroContext;
  market_context: DailyMarketContext;
  data_coverage?: DailyDataCoverage;
  research_signals?: DailyResearchSignals;
  retrograde_context?: DailyRetrogradeContext;
  asset_contexts?: DailyAssetContext[];
  agent_states: DailyAgentState[];
  daily_risk_themes: string[];
  daily_summary: string;
  confidence: string;
  caveats: string[];
  disclaimer: string;
}

export interface AssetCoverageSummary {
  asset: string;
  available_days: number;
  missing_days: number;
  future_placeholder_days: number;
  coverage_status: string;
  notes: string[];
}

export interface ScenarioCoverageSummary {
  total_days: number;
  local_research_days: number;
  placeholder_days: number;
  future_placeholder_days: number;
  mixed_context_days: number;
  astro_daily_available_days: number;
  financial_stress_available_days: number;
  market_daily_available_days: number;
  macro_daily_available_days: number;
  data_sources: string[];
  data_quality_counts: Record<string, number>;
  source_counts: Record<string, number>;
  asset_coverage: AssetCoverageSummary[];
  date_range_mode: string;
  notes: string[];
}

export interface LlmDailyHighlight {
  date: string;
  summary: string;
  key_context: string[];
  agent_focus: string[];
  caveats: string[];
}

export interface LlmAgentInterpretation {
  agent_id: string;
  agent_name: string;
  interpretation: string;
  risk_focus: string[];
  caveats: string[];
}

export interface LlmAssetStressIndicator {
  date: string;
  asset: string;
  sentiment_stress_support: number;
  label: string;
  rationale: string;
  caveats: string[];
}

export interface LlmReportProvenance {
  provider: string;
  model?: string | null;
  base_url_status: string;
  credential_status: string;
  network_call_performed: boolean;
  prompt_template_version: string;
  input_context_hash: string;
  output_validation_status: string;
  safety_check_status: string;
}

export interface LlmScenarioReport {
  status: string;
  provider: string;
  model?: string | null;
  language: ReportLanguage;
  executive_summary: string;
  scenario_reading: string;
  daily_highlights: LlmDailyHighlight[];
  agent_interpretations: LlmAgentInterpretation[];
  asset_stress_indicators?: LlmAssetStressIndicator[];
  risk_themes: string[];
  caveats: string[];
  disclaimer: string;
  raw_text_preview?: string | null;
  provenance: LlmReportProvenance;
}

export interface WorldlineImpactScores {
  sentiment_delta: number;
  narrative_pressure_delta: number;
  leverage_pressure_delta: number;
  liquidity_pressure_delta: number;
  volatility_pressure_delta: number;
  stress_pressure_delta: number;
}

export interface WorldlineAgentEvent {
  agent_id: string;
  agent_name: string;
  what_happened: string;
  why_it_happened: string;
  impact_on_tomorrow: string;
  impact_scores: WorldlineImpactScores;
  confidence: string;
  caveats: string[];
}

export interface WorldlineCausalLink {
  source: string;
  target: string;
  description: string;
  strength: string;
  caveats: string[];
}

export interface WorldlineState {
  sentiment_state: string;
  narrative_pressure: number;
  leverage_pressure: number;
  liquidity_pressure: number;
  volatility_pressure: number;
  stress_pressure: number;
  regime_label?: string | null;
  notes: string[];
}

export interface WorldlineDay {
  date: string;
  day_index: number;
  generation_source?: string;
  chunk_index?: number | null;
  chunk_status?: string | null;
  quality_notes?: string[];
  input_context_summary: string;
  world_state_before: WorldlineState;
  agent_events: WorldlineAgentEvent[];
  causal_links: WorldlineCausalLink[];
  next_day_update: string;
  world_state_after: WorldlineState;
  disclaimer: string;
}

export interface WorldlineGenerationConfig {
  worldline_provider: string;
  worldline_chunk_days: number;
  llm_provider?: string | null;
  llm_real_enabled?: boolean | null;
  llm_base_url?: string | null;
  llm_model?: string | null;
  llm_timeout_seconds?: number | null;
  llm_max_output_tokens?: number | null;
  llm_call_delay_seconds?: number | null;
  report_language?: string | null;
  custom_user_prompt?: string | null;
  preset_id?: string | null;
  preset_name?: string | null;
  credential_status: string;
}

export interface WorldlineSimulation {
  status: string;
  mode: string;
  horizon_days: number;
  days: WorldlineDay[];
  summary: string;
  caveats: string[];
  provenance: Record<string, unknown>;
  generation_config?: WorldlineGenerationConfig | null;
  continuity_status?: string;
  last_regeneration?: Record<string, unknown> | null;
}

export interface ScenarioCreateRequest {
  title: string;
  description?: string | null;
  start_date: string;
  end_date: string;
  assets: string[];
  agent_ids: string[];
  llm_provider: LlmProvider;
  llm_preset_id?: string | null;
  llm_real_enabled?: boolean | null;
  llm_base_url?: string | null;
  llm_model?: string | null;
  llm_api_key?: string | null;
  llm_user_prompt?: string | null;
  llm_timeout_seconds?: number | null;
  llm_max_output_tokens?: number | null;
  llm_call_delay_seconds?: number | null;
  visibility: Visibility;
  mode?: ScenarioMode;
  language?: ReportLanguage;
  worldline_provider?: WorldlineProvider;
  worldline_chunk_days?: 1 | 2 | 3 | 5;
}

export interface ScenarioLlmChunkRequest {
  llm_provider: LlmProvider;
  llm_preset_id?: string | null;
  llm_real_enabled?: boolean | null;
  llm_base_url?: string | null;
  llm_model?: string | null;
  llm_api_key?: string | null;
  llm_user_prompt?: string | null;
  llm_timeout_seconds?: number | null;
  llm_max_output_tokens?: number | null;
  llm_call_delay_seconds?: number | null;
  language?: ReportLanguage;
  chunk_start_date: string;
  chunk_end_date: string;
  chunk_index: number;
  total_chunks: number;
}

export interface ScenarioLlmChunkResponse {
  scenario_id: string;
  chunk_index: number;
  total_chunks: number;
  chunk_start_date: string;
  chunk_end_date: string;
  llm_status: string;
  completed: boolean;
  report: ScenarioReport;
}

export interface ScenarioWorldlineChunkRequest {
  llm_provider: LlmProvider;
  llm_preset_id?: string | null;
  llm_real_enabled?: boolean | null;
  llm_base_url?: string | null;
  llm_model?: string | null;
  llm_api_key?: string | null;
  llm_user_prompt?: string | null;
  llm_timeout_seconds?: number | null;
  llm_max_output_tokens?: number | null;
  llm_call_delay_seconds?: number | null;
  language?: ReportLanguage;
  chunk_start_date: string;
  chunk_end_date: string;
  chunk_index: number;
  total_chunks: number;
  worldline_chunk_days?: 1 | 2 | 3 | 5;
}

export interface ScenarioWorldlineChunkResponse {
  scenario_id: string;
  chunk_index: number;
  total_chunks: number;
  chunk_start_date: string;
  chunk_end_date: string;
  worldline_status: string;
  completed: boolean;
  consecutive_failed_chunk_count: number;
  generation_halted: boolean;
  halt_reason?: string | null;
  report: ScenarioReport;
}

export interface ScenarioWorldlineRegenerateFromRequest {
  start_chunk_index: number;
  note?: string | null;
  regeneration_id?: string | null;
  progressive?: boolean;
  preset_id?: string | null;
  llm_overrides?: {
    real_enabled?: boolean | null;
    base_url?: string | null;
    model?: string | null;
    api_key?: string | null;
    timeout_seconds?: number | null;
    max_output_tokens?: number | null;
    call_delay_seconds?: number | null;
    custom_user_prompt?: string | null;
  } | null;
}

export interface ScenarioWorldlineRegenerateFromResponse {
  scenario_id: string;
  start_chunk_index: number;
  rebuilt_chunk_count: number;
  continuity_status: string;
  regeneration_status: "completed" | "partial_fallback" | "failed_fallback" | string;
  llm_completed_chunk_count: number;
  fallback_chunk_count: number;
  skipped_chunk_count: number;
  report: ScenarioReport;
}

export interface ScenarioSummary {
  scenario_id: string;
  title: string;
  description?: string | null;
  created_at: string;
  start_date: string;
  end_date: string;
  assets: string[];
  agent_ids: string[];
  agent_names: string[];
  visibility: Visibility;
  mode: ScenarioMode;
  language?: ReportLanguage | null;
  worldline_status?: string | null;
  worldline_generation_mode?: string | null;
  worldline_day_count?: number;
  worldline_playable_day_count?: number;
  worldline_generation_halted?: boolean;
  worldline_failed_chunk_count?: number;
  worldline_configuration_fallback_chunk_count?: number;
  worldline_llm_failed_chunk_count?: number;
  llm_report_status?: string | null;
  coverage_total_days?: number | null;
  coverage_local_research_days?: number | null;
  coverage_future_placeholder_days?: number | null;
}

export interface ScenarioReport {
  scenario_id: string;
  title: string;
  description?: string | null;
  created_at: string;
  start_date: string;
  end_date: string;
  assets: string[];
  asset_profiles?: MarketSeriesProfile[];
  agents: AgentProfile[];
  daily_context: Record<string, unknown>;
  simulation_summary: string;
  scenario_summary?: string | null;
  agent_outputs: AgentOutput[];
  risks: string[];
  risk_themes?: string[];
  daily_timeline?: DailyScenarioSnapshot[];
  coverage_summary?: ScenarioCoverageSummary | null;
  llm_report?: LlmScenarioReport | null;
  worldline_simulation?: WorldlineSimulation | null;
  caveats: string[];
  provenance: Record<string, unknown>;
  visibility: Visibility;
  mode: ScenarioMode;
  language?: ReportLanguage | null;
  markdown_report: string;
  disclaimer: string;
}

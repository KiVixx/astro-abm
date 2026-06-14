export type Visibility = "private" | "public";
export type ScenarioMode = "daily_association_only";
export type LlmProvider = "mock" | "openai_compatible";
export type ReportLanguage = "en" | "zh-Hant";

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
  risk_themes: string[];
  caveats: string[];
  disclaimer: string;
  raw_text_preview?: string | null;
  provenance: LlmReportProvenance;
}

export interface ScenarioCreateRequest {
  title: string;
  description?: string | null;
  start_date: string;
  end_date: string;
  assets: string[];
  agent_ids: string[];
  llm_provider: LlmProvider;
  llm_real_enabled?: boolean | null;
  llm_base_url?: string | null;
  llm_model?: string | null;
  llm_api_key?: string | null;
  llm_timeout_seconds?: number | null;
  llm_max_output_tokens?: number | null;
  visibility: Visibility;
  mode?: ScenarioMode;
  language?: ReportLanguage;
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
  caveats: string[];
  provenance: Record<string, unknown>;
  visibility: Visibility;
  mode: ScenarioMode;
  language?: ReportLanguage | null;
  markdown_report: string;
  disclaimer: string;
}

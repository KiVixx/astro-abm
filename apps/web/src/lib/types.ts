export type Visibility = "private" | "public";
export type ScenarioMode = "daily_association_only";
export type LlmProvider = "mock" | "openai_compatible";

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

export interface DailyAgentState {
  agent_id: string;
  agent_name: string;
  mood: string;
  risk_appetite: string;
  likely_reaction: string;
  attention_triggers: string[];
  caveats: string[];
}

export interface DailyScenarioSnapshot {
  date: string;
  day_index: number;
  assets: string[];
  astro_context: DailyAstroContext;
  market_context: DailyMarketContext;
  agent_states: DailyAgentState[];
  daily_risk_themes: string[];
  daily_summary: string;
  confidence: string;
  caveats: string[];
  disclaimer: string;
}

export interface ScenarioCreateRequest {
  title: string;
  description?: string | null;
  start_date: string;
  end_date: string;
  assets: string[];
  agent_ids: string[];
  llm_provider: LlmProvider;
  llm_base_url?: string | null;
  llm_model?: string | null;
  visibility: Visibility;
  mode?: ScenarioMode;
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
}

export interface ScenarioReport {
  scenario_id: string;
  title: string;
  description?: string | null;
  created_at: string;
  start_date: string;
  end_date: string;
  assets: string[];
  agents: AgentProfile[];
  daily_context: Record<string, unknown>;
  simulation_summary: string;
  scenario_summary?: string | null;
  agent_outputs: AgentOutput[];
  risks: string[];
  risk_themes?: string[];
  daily_timeline?: DailyScenarioSnapshot[];
  caveats: string[];
  provenance: Record<string, unknown>;
  visibility: Visibility;
  mode: ScenarioMode;
  markdown_report: string;
  disclaimer: string;
}

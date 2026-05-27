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
  agent_outputs: AgentOutput[];
  risks: string[];
  caveats: string[];
  provenance: Record<string, unknown>;
  visibility: Visibility;
  mode: ScenarioMode;
  markdown_report: string;
  disclaimer: string;
}

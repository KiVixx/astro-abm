import type {
  DailyAgentState,
  DailyDataCoverage,
  DailyResearchSignals,
  DailyScenarioSnapshot,
  ScenarioReport,
} from "./types";
import { assetStressPointForSnapshot } from "./assetStressSentiment";

export type WorkbenchNodeType =
  | "agent"
  | "astro"
  | "stress"
  | "volatility"
  | "liquidity"
  | "data_quality"
  | "asset"
  | "risk";

export type WorkbenchEdgeType =
  | "agent_attention"
  | "context_to_asset"
  | "context_to_risk";

export interface WorkbenchNode {
  id: string;
  type: WorkbenchNodeType;
  label: string;
  subtitle?: string;
  detail?: string;
  x: number;
  y: number;
  payload?: unknown;
}

export interface WorkbenchEdge {
  id: string;
  source: string;
  target: string;
  type: WorkbenchEdgeType;
  label?: string;
}

export interface WorkbenchGraph {
  nodes: WorkbenchNode[];
  edges: WorkbenchEdge[];
  width: number;
  height: number;
}

export interface AgentNodePayload {
  kind: "agent";
  state: DailyAgentState;
}

export interface ContextNodePayload {
  kind: "context";
  title: string;
  value: string;
  detail: string;
  notes: string[];
}

export interface AssetNodePayload {
  kind: "asset";
  asset: string;
  date: string;
  summary: string;
  sentimentStressSupport: number;
  sentimentStressSource: string;
  color: string;
}

export interface RiskNodePayload {
  kind: "risk";
  theme: string;
  date: string;
  caveats: string[];
}

const GRAPH_WIDTH = 1120;
const GRAPH_HEIGHT = 720;
const TOP_MARGIN = 90;
const BOTTOM_MARGIN = 620;
const AGENT_X = 150;
const CONTEXT_X = 555;
const RIGHT_X = 930;

export function getDailyDataCoverage(
  snapshot: DailyScenarioSnapshot,
): DailyDataCoverage {
  return (
    snapshot.data_coverage || {
      astro_daily: "unknown",
      financial_stress_daily: "unknown",
      market_daily: "unknown",
      macro_daily: "unknown",
      source: "legacy_report",
      notes: ["This saved report does not include data coverage fields."],
    }
  );
}

export function getDailyResearchSignals(
  snapshot: DailyScenarioSnapshot,
): DailyResearchSignals {
  return (
    snapshot.research_signals || {
      stress_regime: snapshot.market_context.stress_regime || "unknown",
      volatility_regime: snapshot.market_context.volatility_regime || "unknown",
      liquidity_regime: snapshot.market_context.liquidity_regime || "unknown",
      astro_activity: snapshot.astro_context.intensity || "unknown",
      data_quality: "legacy_report",
    }
  );
}

function stableId(...parts: string[]): string {
  return parts
    .join("_")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 96);
}

function spacedY(count: number, index: number): number {
  if (count <= 1) {
    return (TOP_MARGIN + BOTTOM_MARGIN) / 2;
  }
  return TOP_MARGIN + ((BOTTOM_MARGIN - TOP_MARGIN) * index) / (count - 1);
}

function trimText(value: string, length = 72): string {
  if (value.length <= length) {
    return value;
  }
  return `${value.slice(0, length - 1)}...`;
}

function buildContextNodes(snapshot: DailyScenarioSnapshot): WorkbenchNode[] {
  const coverage = getDailyDataCoverage(snapshot);
  const signals = getDailyResearchSignals(snapshot);
  const contextRows: Array<Omit<WorkbenchNode, "x" | "y">> = [
    {
      id: "context_astro",
      type: "astro",
      label: "Astro Activity",
      subtitle: signals.astro_activity,
      detail: snapshot.astro_context.summary,
      payload: {
        kind: "context",
        title: "Astro Activity",
        value: signals.astro_activity,
        detail: snapshot.astro_context.summary,
        notes: snapshot.astro_context.event_tags,
      } satisfies ContextNodePayload,
    },
    {
      id: "context_stress",
      type: "stress",
      label: "Stress Regime",
      subtitle: signals.stress_regime,
      detail: snapshot.market_context.summary,
      payload: {
        kind: "context",
        title: "Stress Regime",
        value: signals.stress_regime,
        detail: snapshot.market_context.summary,
        notes: coverage.notes,
      } satisfies ContextNodePayload,
    },
    {
      id: "context_volatility",
      type: "volatility",
      label: "Volatility Regime",
      subtitle: signals.volatility_regime,
      detail: snapshot.market_context.summary,
      payload: {
        kind: "context",
        title: "Volatility Regime",
        value: signals.volatility_regime,
        detail: snapshot.market_context.summary,
        notes: coverage.notes,
      } satisfies ContextNodePayload,
    },
    {
      id: "context_liquidity",
      type: "liquidity",
      label: "Liquidity Regime",
      subtitle: signals.liquidity_regime,
      detail: snapshot.market_context.summary,
      payload: {
        kind: "context",
        title: "Liquidity Regime",
        value: signals.liquidity_regime,
        detail: snapshot.market_context.summary,
        notes: coverage.notes,
      } satisfies ContextNodePayload,
    },
    {
      id: "context_data_quality",
      type: "data_quality",
      label: "Data Quality",
      subtitle: signals.data_quality,
      detail: `Source: ${coverage.source}`,
      payload: {
        kind: "context",
        title: "Data Quality",
        value: signals.data_quality,
        detail: `Source: ${coverage.source}`,
        notes: coverage.notes,
      } satisfies ContextNodePayload,
    },
  ];

  return contextRows.map((node, index) => ({
    ...node,
    x: CONTEXT_X,
    y: spacedY(contextRows.length, index),
  }));
}

function buildRiskNodes(snapshot: DailyScenarioSnapshot): WorkbenchNode[] {
  const riskThemes = snapshot.daily_risk_themes.length
    ? snapshot.daily_risk_themes
    : ["scenario_review"];
  const visibleThemes = riskThemes.slice(0, 7);
  const hasMore = riskThemes.length > visibleThemes.length;
  const rows = hasMore
    ? [...visibleThemes, `${riskThemes.length - visibleThemes.length} more themes`]
    : visibleThemes;

  return rows.map((theme, index) => ({
    id: stableId("risk", theme, String(index)),
    type: "risk",
    label: trimText(theme.replaceAll("_", " "), 34),
    subtitle: "Risk theme",
    detail: theme,
    x: RIGHT_X,
    y: spacedY(rows.length + snapshot.assets.length, snapshot.assets.length + index),
    payload: {
      kind: "risk",
      theme,
      date: snapshot.date,
      caveats: snapshot.caveats,
    } satisfies RiskNodePayload,
  }));
}

function buildAssetNodes(report: ScenarioReport, snapshot: DailyScenarioSnapshot) {
  const assets = snapshot.assets.length ? snapshot.assets : report.assets;
  return assets.map((asset, index) => {
    const stressPoint = assetStressPointForSnapshot(snapshot, asset, index);
    return {
      id: stableId("asset", asset),
      type: "asset" as const,
      label: asset,
      subtitle: `${stressPoint.value.toFixed(1)}`,
      detail: snapshot.market_context.summary,
      x: RIGHT_X,
      y: spacedY(assets.length + snapshot.daily_risk_themes.length, index),
      payload: {
        kind: "asset",
        asset,
        date: snapshot.date,
        summary: snapshot.market_context.summary,
        sentimentStressSupport: stressPoint.value,
        sentimentStressSource: stressPoint.source,
        color: stressPoint.color,
      } satisfies AssetNodePayload,
    };
  });
}

function buildAgentNodes(snapshot: DailyScenarioSnapshot): WorkbenchNode[] {
  return snapshot.agent_states.map((state, index) => ({
    id: stableId("agent", state.agent_id),
    type: "agent",
    label: trimText(state.agent_name, 28),
    subtitle: state.risk_appetite,
    detail: state.likely_reaction,
    x: AGENT_X,
    y: spacedY(snapshot.agent_states.length, index),
    payload: {
      kind: "agent",
      state,
    } satisfies AgentNodePayload,
  }));
}

function buildEdges(nodes: WorkbenchNode[]): WorkbenchEdge[] {
  const agents = nodes.filter((node) => node.type === "agent");
  const contextTargets = ["context_astro", "context_stress", "context_volatility", "context_liquidity"];
  const assetTargets = nodes.filter((node) => node.type === "asset");
  const riskTargets = nodes.filter((node) => node.type === "risk");
  const edges: WorkbenchEdge[] = [];

  for (const agent of agents) {
    for (const contextId of contextTargets) {
      edges.push({
        id: stableId("edge", agent.id, contextId),
        source: agent.id,
        target: contextId,
        type: "agent_attention",
      });
    }
  }

  for (const contextId of ["context_stress", "context_volatility", "context_liquidity"]) {
    for (const asset of assetTargets) {
      edges.push({
        id: stableId("edge", contextId, asset.id),
        source: contextId,
        target: asset.id,
        type: "context_to_asset",
      });
    }
  }

  for (const contextId of ["context_astro", "context_stress", "context_volatility", "context_data_quality"]) {
    for (const risk of riskTargets) {
      edges.push({
        id: stableId("edge", contextId, risk.id),
        source: contextId,
        target: risk.id,
        type: "context_to_risk",
      });
    }
  }

  return edges;
}

export function buildWorkbenchGraph(
  report: ScenarioReport,
  snapshot: DailyScenarioSnapshot,
): WorkbenchGraph {
  const nodes = [
    ...buildAgentNodes(snapshot),
    ...buildContextNodes(snapshot),
    ...buildAssetNodes(report, snapshot),
    ...buildRiskNodes(snapshot),
  ];

  return {
    nodes,
    edges: buildEdges(nodes),
    width: GRAPH_WIDTH,
    height: GRAPH_HEIGHT,
  };
}

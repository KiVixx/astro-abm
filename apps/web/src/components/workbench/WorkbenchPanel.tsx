import type {
  DailyScenarioSnapshot,
  DailyRetrogradeBodyContext,
  WorldlineDay,
  WorldlineSimulation,
} from "@/lib/types";
import { SafetyPhrases } from "../SafetyPhrases";
import { WorldlinePanel } from "./WorldlinePanel";
import {
  getDailyDataCoverage,
  getDailyResearchSignals,
  type AgentNodePayload,
  type AssetNodePayload,
  type ContextNodePayload,
  type RiskNodePayload,
  type WorkbenchEdge,
  type WorkbenchGraph,
  type WorkbenchNode,
} from "@/lib/workbenchGraph";
import { edgeEndpointIds } from "@/lib/workbenchForceGraph";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";
import type { RetrogradeBody } from "@/lib/retrograde";
import { retrogradeBodyLabel } from "./RetrogradeBodySelector";

interface WorkbenchPanelProps {
  snapshot: DailyScenarioSnapshot;
  selectedNode: WorkbenchNode | null;
  selectedEdge?: WorkbenchEdge | null;
  graph?: WorkbenchGraph | null;
  worldlineDay?: WorldlineDay | null;
  worldlineSimulation?: WorldlineSimulation | null;
  worldlinePrimary?: boolean;
  onRegenerateWorldline?: () => void;
  canRegenerateWorldline?: boolean;
  resumeRegeneration?: boolean;
  retryHaltedGeneration?: boolean;
  regenerationActive?: boolean;
  regenerationMessage?: string;
  regenerationError?: string | null;
  selectedRetrogradeBodies?: RetrogradeBody[];
}

function RetrogradeBodyReadout({
  context,
}: {
  context: DailyRetrogradeBodyContext;
}) {
  const { t } = useI18n();
  const body = context.body as RetrogradeBody;
  const speed = context.lon_speed_deg_day;
  return (
    <div className="retrograde-readout-row">
      <div className="retrograde-readout-heading">
        <strong>{retrogradeBodyLabel(body, t)}</strong>
        <span>{context.body}</span>
      </div>
      <div className="tag-row">
        <span className={`tag ${context.is_retrograde ? "is-retrograde" : ""}`}>
          {formatEnumLabel(t, "retrograde_phase", context.phase)}
        </span>
        <span className="tag">
          {t("retrograde.longitudeSpeed")}: {speed === null || speed === undefined
            ? t("value.common.unknown")
            : `${speed.toFixed(6)}°/${t("common.day")}`}
        </span>
      </div>
      <dl className="retrograde-readout-facts">
        <div>
          <dt>{t("retrograde.nearestStation")}</dt>
          <dd>
            {context.nearest_station_type
              ? formatEnumLabel(t, "station_type", context.nearest_station_type)
              : t("value.common.unknown")}
          </dd>
        </div>
        <div>
          <dt>{t("retrograde.stationTime")}</dt>
          <dd>{context.nearest_station_ts || t("value.common.unknown")}</dd>
        </div>
        <div>
          <dt>{t("retrograde.nearestDistance")}</dt>
          <dd>
            {context.days_to_station_nearest ?? t("value.common.unknown")} {t("retrograde.days")}
          </dd>
        </div>
        <div>
          <dt>{t("retrograde.cycle")}</dt>
          <dd>{context.cycle_id || t("value.common.unknown")}</dd>
        </div>
        <div>
          <dt>{t("common.source")}</dt>
          <dd>{context.source}</dd>
        </div>
        <div>
          <dt>{t("common.quality")}</dt>
          <dd>{context.data_quality}</dd>
        </div>
      </dl>
      {context.notes.length ? <BulletList items={context.notes} /> : null}
    </div>
  );
}

function RetrogradeContextPanel({
  snapshot,
  selectedBodies,
}: {
  snapshot: DailyScenarioSnapshot;
  selectedBodies: RetrogradeBody[];
}) {
  const { t } = useI18n();
  const context = snapshot.retrograde_context;
  const bodies = selectedBodies
    .map((body) => context?.bodies.find((item) => item.body === body))
    .filter((item): item is DailyRetrogradeBodyContext => Boolean(item));
  return (
    <details className="retrograde-readout" open>
      <summary>
        {t("retrograde.dailyDetails")} · {snapshot.date} ({bodies.length})
      </summary>
      <div className="retrograde-readout-content">
        {!selectedBodies.length ? (
          <p className="muted">{t("retrograde.noBodiesSelected")}</p>
        ) : !context?.bodies.length ? (
          <p className="muted">{t("retrograde.noData")}</p>
        ) : (
          bodies.map((body) => <RetrogradeBodyReadout context={body} key={body.body} />)
        )}
        {context?.notes.length ? (
          <div className="retrograde-readout-notes">
            <strong>{t("workbench.notes")}</strong>
            <BulletList items={context.notes} />
          </div>
        ) : null}
        <p className="retrograde-context-disclaimer">
          {t("retrograde.contextDisclaimer")}
        </p>
      </div>
    </details>
  );
}

function hasKind<T extends string>(
  payload: unknown,
  kind: T,
): payload is { kind: T } {
  return typeof payload === "object" && payload !== null && "kind" in payload
    ? (payload as { kind?: string }).kind === kind
    : false;
}

function BulletList({ items }: { items: string[] }) {
  const { t } = useI18n();
  if (!items.length) {
    return <p className="muted">{t("workbench.noEntries")}</p>;
  }
  return (
    <ul>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function CoverageTags({ snapshot }: { snapshot: DailyScenarioSnapshot }) {
  const { t } = useI18n();
  const coverage = getDailyDataCoverage(snapshot);
  const signals = getDailyResearchSignals(snapshot);

  return (
    <div className="tag-row">
      <span className="tag">
        {t("common.source")}: {formatEnumLabel(t, "data_source", coverage.source)}
      </span>
      <span className="tag">
        {t("common.astro")}:{" "}
        {formatEnumLabel(t, "coverage_status", coverage.astro_daily)}
      </span>
      <span className="tag">
        {t("common.stress")}:{" "}
        {formatEnumLabel(t, "coverage_status", coverage.financial_stress_daily)}
      </span>
      <span className="tag">
        {t("common.market")}:{" "}
        {formatEnumLabel(t, "coverage_status", coverage.market_daily)}
      </span>
      <span className="tag">
        {t("common.macro")}:{" "}
        {formatEnumLabel(t, "coverage_status", coverage.macro_daily)}
      </span>
      <span className="tag">
        {t("common.quality")}:{" "}
        {formatEnumLabel(t, "data_quality", signals.data_quality)}
      </span>
    </div>
  );
}

function ResearchSignalTags({ snapshot }: { snapshot: DailyScenarioSnapshot }) {
  const { t } = useI18n();
  const signals = getDailyResearchSignals(snapshot);
  return (
    <div className="tag-row">
      <span className="tag">
        {t("workbench.contextStress")}:{" "}
        {formatEnumLabel(t, "stress_regime", signals.stress_regime)}
      </span>
      <span className="tag">
        {t("common.volatility")}:{" "}
        {formatEnumLabel(t, "volatility_regime", signals.volatility_regime)}
      </span>
      <span className="tag">
        {t("common.liquidity")}:{" "}
        {formatEnumLabel(t, "liquidity_regime", signals.liquidity_regime)}
      </span>
      <span className="tag">
        {t("common.astro")}: {formatEnumLabel(t, "astro_intensity", signals.astro_activity)}
      </span>
    </div>
  );
}

function OverviewPanel({ snapshot }: { snapshot: DailyScenarioSnapshot }) {
  const { t } = useI18n();
  const coverage = getDailyDataCoverage(snapshot);

  return (
    <div className="stack">
      <div>
        <h2>{snapshot.date}</h2>
        <p>{snapshot.daily_summary}</p>
      </div>
      <div>
        <h3>{t("report.researchSignals")}</h3>
        <ResearchSignalTags snapshot={snapshot} />
      </div>
      <div>
        <h3>{t("report.dataCoverage")}</h3>
        <CoverageTags snapshot={snapshot} />
        <BulletList items={coverage.notes} />
      </div>
      <div>
        <h3>{t("report.agentStates")}</h3>
        <div className="stack">
          {snapshot.agent_states.map((state) => (
            <div className="nested-panel" key={state.agent_id}>
              <strong>{formatAgentName(t, state.agent_id, state.agent_name)}</strong>
              <p>{state.likely_reaction}</p>
              <div className="tag-row">
                <span className="tag">
                  {t("common.mood")}: {formatEnumLabel(t, "agent_mood", state.mood)}
                </span>
                <span className="tag">
                  {t("common.riskAppetite")}: {formatEnumLabel(
                    t,
                    "agent_level",
                    state.risk_appetite,
                  )}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3>{t("report.riskThemes")}</h3>
        <BulletList items={snapshot.daily_risk_themes} />
      </div>
      <div>
        <h3>{t("report.caveats")}</h3>
        <BulletList items={snapshot.caveats} />
      </div>
    </div>
  );
}

function AgentNodePanel({ payload }: { payload: AgentNodePayload }) {
  const { t } = useI18n();
  const { state } = payload;
  return (
    <div className="stack">
      <div>
        <h2>{formatAgentName(t, state.agent_id, state.agent_name)}</h2>
        <p className="muted">{t("workbench.agentGroupState")}</p>
      </div>
      <div className="tag-row">
        <span className="tag">
          {t("common.mood")}: {formatEnumLabel(t, "agent_mood", state.mood)}
        </span>
        <span className="tag">
          {t("common.riskAppetite")}: {formatEnumLabel(t, "agent_level", state.risk_appetite)}
        </span>
      </div>
      <div>
        <h3>{t("workbench.likelyReaction")}</h3>
        <p>{state.likely_reaction}</p>
      </div>
      <div>
        <h3>{t("workbench.attentionTriggers")}</h3>
        <BulletList items={state.attention_triggers} />
      </div>
      <div>
        <h3>{t("report.caveats")}</h3>
        <BulletList items={state.caveats} />
      </div>
    </div>
  );
}

function ContextNodePanel({ payload }: { payload: ContextNodePayload }) {
  const { t } = useI18n();
  const titleMap: Record<string, string> = {
    "Astro Activity": "legend.astro",
    "Stress Regime": "workbench.contextStress",
    "Volatility Regime": "workbench.contextVolatility",
    "Liquidity Regime": "workbench.contextLiquidity",
    "Data Quality": "legend.data",
  };
  const valueGroupMap: Record<string, string> = {
    "Astro Activity": "astro_intensity",
    "Stress Regime": "stress_regime",
    "Volatility Regime": "volatility_regime",
    "Liquidity Regime": "liquidity_regime",
    "Data Quality": "data_quality",
  };
  return (
    <div className="stack">
      <div>
        <h2>{titleMap[payload.title] ? t(titleMap[payload.title]) : payload.title}</h2>
        <p className="muted">
          {formatEnumLabel(t, valueGroupMap[payload.title] || "", payload.value)}
        </p>
      </div>
      <p>{payload.detail}</p>
      <div>
        <h3>{t("workbench.notes")}</h3>
        <BulletList items={payload.notes} />
      </div>
    </div>
  );
}

function AssetNodePanel({ payload }: { payload: AssetNodePayload }) {
  const { t } = useI18n();
  const sourceLabel =
    payload.sentimentStressSource === "llm_scenario_metric"
      ? t("workbench.llmMetric")
      : payload.sentimentStressSource === "timeline_metric"
        ? t("workbench.timelineMetric")
        : t("workbench.mockMetric");
  return (
    <div className="stack">
      <div>
        <h2>{payload.asset}</h2>
        <p className="muted">{t("workbench.assetContextFor")} {payload.date}</p>
      </div>
      <p>{payload.summary}</p>
      <div className="tag-row">
        <span className="tag">
          {t("workbench.assetStressSentiment")}:{" "}
          {payload.sentimentStressSupport.toFixed(1)}
        </span>
        <span className="tag">{sourceLabel}</span>
      </div>
      <p className="notice">
        {t("workbench.assetNotice")}
      </p>
    </div>
  );
}

function RiskNodePanel({ payload }: { payload: RiskNodePayload }) {
  const { t } = useI18n();
  return (
    <div className="stack">
      <div>
        <h2>{payload.theme.replaceAll("_", " ")}</h2>
        <p className="muted">{t("workbench.riskThemeFor")} {payload.date}</p>
      </div>
      <div>
        <h3>{t("report.caveats")}</h3>
        <BulletList items={payload.caveats} />
      </div>
    </div>
  );
}

function displayWorkbenchNodeLabel(
  t: (key: string, fallback?: string) => string,
  node?: WorkbenchNode,
) {
  if (!node) {
    return t("value.common.unknown", "Unknown");
  }
  const payload = node.payload;
  if (payload && hasKind(payload, "context")) {
    const titleMap: Record<string, string> = {
      "Astro Activity": "legend.astro",
      "Stress Regime": "workbench.contextStress",
      "Volatility Regime": "workbench.contextVolatility",
      "Liquidity Regime": "workbench.contextLiquidity",
      "Data Quality": "legend.data",
    };
    const contextPayload = payload as ContextNodePayload;
    return t(titleMap[contextPayload.title] || "", node.label);
  }
  if (payload && hasKind(payload, "agent")) {
    const agentPayload = payload as AgentNodePayload;
    return formatAgentName(
      t,
      agentPayload.state.agent_id,
      agentPayload.state.agent_name,
    );
  }
  return node.label;
}

function EdgePanel({
  edge,
  graph,
}: {
  edge: WorkbenchEdge;
  graph?: WorkbenchGraph | null;
}) {
  const { t } = useI18n();
  const [sourceId, targetId] = edgeEndpointIds(edge);
  const source = graph?.nodes.find((node) => node.id === sourceId);
  const target = graph?.nodes.find((node) => node.id === targetId);

  return (
    <div className="stack">
      <div>
        <h2>{t("workbench.selectedRelationship")}</h2>
        <p className="muted">{t("workbench.relationshipNotice")}</p>
      </div>
      <div className="nested-panel">
        <strong>{displayWorkbenchNodeLabel(t, source)}</strong>
        <p className="muted">{t("workbench.sourceNode")}</p>
      </div>
      <div className="nested-panel">
        <strong>{displayWorkbenchNodeLabel(t, target)}</strong>
        <p className="muted">{t("workbench.targetNode")}</p>
      </div>
      <div className="tag-row">
        <span className="tag">
          {t("workbench.edgeType")}: {formatEnumLabel(t, "edge_type", edge.type)}
        </span>
      </div>
    </div>
  );
}

export function WorkbenchPanel({
  graph,
  selectedEdge,
  selectedNode,
  snapshot,
  worldlineDay,
  worldlineSimulation,
  worldlinePrimary = false,
  onRegenerateWorldline,
  canRegenerateWorldline = true,
  resumeRegeneration = false,
  retryHaltedGeneration = false,
  regenerationActive = false,
  regenerationMessage = "",
  regenerationError = null,
  selectedRetrogradeBodies = [],
}: WorkbenchPanelProps) {
  const { t } = useI18n();
  const payload = selectedNode?.payload;
  const selectedLabel = selectedEdge
    ? t("workbench.selectedRelationship")
    : displayWorkbenchNodeLabel(t, selectedNode || undefined);

  return (
    <aside className="workbench-card workbench-panel">
      <div className="workbench-card-header">
        <span className="workbench-console-signal" aria-hidden="true" />
        <div>
          <p className="pixel-kicker workbench-module-kicker">
            {t("workbench.consoleKicker")}
          </p>
          <h2>{worldlinePrimary ? t("worldline.console") : t("workbench.panelTitle")}</h2>
          <p className="muted">
            {selectedNode || selectedEdge ? selectedLabel : t("workbench.dailyOverview")}{" "}
            {t("workbench.forDate")} {snapshot.date}
          </p>
        </div>
      </div>
      {worldlinePrimary ? (
        <WorldlinePanel
          canRegenerateWorldline={canRegenerateWorldline}
          onRegenerateWorldline={onRegenerateWorldline}
          resumeRegeneration={resumeRegeneration}
          retryHaltedGeneration={retryHaltedGeneration}
          primary
          regenerationActive={regenerationActive}
          regenerationError={regenerationError}
          regenerationMessage={regenerationMessage}
          worldlineDay={worldlineDay}
          worldlineSimulation={worldlineSimulation}
        />
      ) : null}
      {selectedEdge ? (
        <EdgePanel edge={selectedEdge} graph={graph} />
      ) : payload && hasKind(payload, "agent") ? (
        <AgentNodePanel payload={payload as AgentNodePayload} />
      ) : payload && hasKind(payload, "context") ? (
        <ContextNodePanel payload={payload as ContextNodePayload} />
      ) : payload && hasKind(payload, "asset") ? (
        <AssetNodePanel payload={payload as AssetNodePayload} />
      ) : payload && hasKind(payload, "risk") ? (
        <RiskNodePanel payload={payload as RiskNodePayload} />
      ) : (
        <OverviewPanel snapshot={snapshot} />
      )}
      <RetrogradeContextPanel
        selectedBodies={selectedRetrogradeBodies}
        snapshot={snapshot}
      />
      {!worldlinePrimary ? (
        <WorldlinePanel
          canRegenerateWorldline={canRegenerateWorldline}
          onRegenerateWorldline={onRegenerateWorldline}
          resumeRegeneration={resumeRegeneration}
          retryHaltedGeneration={retryHaltedGeneration}
          regenerationActive={regenerationActive}
          regenerationError={regenerationError}
          regenerationMessage={regenerationMessage}
          worldlineDay={worldlineDay}
          worldlineSimulation={worldlineSimulation}
        />
      ) : null}
      <div className="notice workbench-disclaimer">
        <SafetyPhrases />
        <p>{snapshot.disclaimer}</p>
      </div>
    </aside>
  );
}

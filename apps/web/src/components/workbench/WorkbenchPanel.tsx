import type { DailyScenarioSnapshot } from "@/lib/types";
import { SafetyPhrases } from "../SafetyPhrases";
import {
  getDailyDataCoverage,
  getDailyResearchSignals,
  type AgentNodePayload,
  type AssetNodePayload,
  type ContextNodePayload,
  type RiskNodePayload,
  type WorkbenchNode,
} from "@/lib/workbenchGraph";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface WorkbenchPanelProps {
  snapshot: DailyScenarioSnapshot;
  selectedNode: WorkbenchNode | null;
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
      <span className="tag">{t("common.astro")}: {signals.astro_activity}</span>
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
                <span className="tag">{t("common.mood")}: {state.mood}</span>
                <span className="tag">
                  {t("common.riskAppetite")}: {state.risk_appetite}
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
        <span className="tag">{t("common.mood")}: {state.mood}</span>
        <span className="tag">{t("common.riskAppetite")}: {state.risk_appetite}</span>
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
  return (
    <div className="stack">
      <div>
        <h2>{titleMap[payload.title] ? t(titleMap[payload.title]) : payload.title}</h2>
        <p className="muted">{payload.value}</p>
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
        <span className="tag">
          {payload.sentimentStressSource === "mock_demo"
            ? t("workbench.mockMetric")
            : t("workbench.timelineMetric")}
        </span>
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

export function WorkbenchPanel({ snapshot, selectedNode }: WorkbenchPanelProps) {
  const { t } = useI18n();
  const payload = selectedNode?.payload;
  const selectedNodeLabel =
    payload && hasKind(payload, "context")
      ? t(
          {
            "Astro Activity": "legend.astro",
            "Stress Regime": "workbench.contextStress",
            "Volatility Regime": "workbench.contextVolatility",
            "Liquidity Regime": "workbench.contextLiquidity",
            "Data Quality": "legend.data",
          }[(payload as ContextNodePayload).title] || "",
          selectedNode?.label,
        )
      : payload && hasKind(payload, "agent")
        ? formatAgentName(
            t,
            (payload as AgentNodePayload).state.agent_id,
            (payload as AgentNodePayload).state.agent_name,
          )
      : selectedNode?.label;

  return (
    <aside className="workbench-card workbench-panel">
      <div className="workbench-card-header">
        <div>
          <h2>{t("workbench.panelTitle")}</h2>
          <p className="muted">
            {selectedNode ? selectedNodeLabel : t("workbench.dailyOverview")}{" "}
            {t("workbench.forDate")} {snapshot.date}
          </p>
        </div>
      </div>
      {payload && hasKind(payload, "agent") ? (
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
      <div className="notice workbench-disclaimer">
        <SafetyPhrases />
        <p>{snapshot.disclaimer}</p>
      </div>
    </aside>
  );
}

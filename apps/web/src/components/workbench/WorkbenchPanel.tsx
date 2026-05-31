import type { DailyScenarioSnapshot } from "@/lib/types";
import {
  getDailyDataCoverage,
  getDailyResearchSignals,
  type AgentNodePayload,
  type AssetNodePayload,
  type ContextNodePayload,
  type RiskNodePayload,
  type WorkbenchNode,
} from "@/lib/workbenchGraph";

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
  if (!items.length) {
    return <p className="muted">No entries for this section.</p>;
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
  const coverage = getDailyDataCoverage(snapshot);
  const signals = getDailyResearchSignals(snapshot);

  return (
    <div className="tag-row">
      <span className="tag">source: {coverage.source}</span>
      <span className="tag">astro: {coverage.astro_daily}</span>
      <span className="tag">stress: {coverage.financial_stress_daily}</span>
      <span className="tag">market: {coverage.market_daily}</span>
      <span className="tag">macro: {coverage.macro_daily}</span>
      <span className="tag">quality: {signals.data_quality}</span>
    </div>
  );
}

function ResearchSignalTags({ snapshot }: { snapshot: DailyScenarioSnapshot }) {
  const signals = getDailyResearchSignals(snapshot);
  return (
    <div className="tag-row">
      <span className="tag">stress regime: {signals.stress_regime}</span>
      <span className="tag">volatility: {signals.volatility_regime}</span>
      <span className="tag">liquidity: {signals.liquidity_regime}</span>
      <span className="tag">astro activity: {signals.astro_activity}</span>
    </div>
  );
}

function OverviewPanel({ snapshot }: { snapshot: DailyScenarioSnapshot }) {
  const coverage = getDailyDataCoverage(snapshot);

  return (
    <div className="stack">
      <div>
        <h2>{snapshot.date}</h2>
        <p>{snapshot.daily_summary}</p>
      </div>
      <div>
        <h3>Research signals</h3>
        <ResearchSignalTags snapshot={snapshot} />
      </div>
      <div>
        <h3>Data coverage</h3>
        <CoverageTags snapshot={snapshot} />
        <BulletList items={coverage.notes} />
      </div>
      <div>
        <h3>Agent states</h3>
        <div className="stack">
          {snapshot.agent_states.map((state) => (
            <div className="nested-panel" key={state.agent_id}>
              <strong>{state.agent_name}</strong>
              <p>{state.likely_reaction}</p>
              <div className="tag-row">
                <span className="tag">{state.mood}</span>
                <span className="tag">{state.risk_appetite}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3>Risk themes</h3>
        <BulletList items={snapshot.daily_risk_themes} />
      </div>
      <div>
        <h3>Caveats</h3>
        <BulletList items={snapshot.caveats} />
      </div>
    </div>
  );
}

function AgentNodePanel({ payload }: { payload: AgentNodePayload }) {
  const { state } = payload;
  return (
    <div className="stack">
      <div>
        <h2>{state.agent_name}</h2>
        <p className="muted">Agent group state</p>
      </div>
      <div className="tag-row">
        <span className="tag">mood: {state.mood}</span>
        <span className="tag">risk appetite: {state.risk_appetite}</span>
      </div>
      <div>
        <h3>Likely reaction</h3>
        <p>{state.likely_reaction}</p>
      </div>
      <div>
        <h3>Attention triggers</h3>
        <BulletList items={state.attention_triggers} />
      </div>
      <div>
        <h3>Caveats</h3>
        <BulletList items={state.caveats} />
      </div>
    </div>
  );
}

function ContextNodePanel({ payload }: { payload: ContextNodePayload }) {
  return (
    <div className="stack">
      <div>
        <h2>{payload.title}</h2>
        <p className="muted">{payload.value}</p>
      </div>
      <p>{payload.detail}</p>
      <div>
        <h3>Notes</h3>
        <BulletList items={payload.notes} />
      </div>
    </div>
  );
}

function AssetNodePanel({ payload }: { payload: AssetNodePayload }) {
  return (
    <div className="stack">
      <div>
        <h2>{payload.asset}</h2>
        <p className="muted">Asset context for {payload.date}</p>
      </div>
      <p>{payload.summary}</p>
      <p className="notice">
        This node shows scenario context only. It is not financial advice and not
        a trading signal.
      </p>
    </div>
  );
}

function RiskNodePanel({ payload }: { payload: RiskNodePayload }) {
  return (
    <div className="stack">
      <div>
        <h2>{payload.theme.replaceAll("_", " ")}</h2>
        <p className="muted">Risk theme for {payload.date}</p>
      </div>
      <div>
        <h3>Caveats</h3>
        <BulletList items={payload.caveats} />
      </div>
    </div>
  );
}

export function WorkbenchPanel({ snapshot, selectedNode }: WorkbenchPanelProps) {
  const payload = selectedNode?.payload;

  return (
    <aside className="workbench-card workbench-panel">
      <div className="workbench-card-header">
        <div>
          <h2>Workbench Panel</h2>
          <p className="muted">
            {selectedNode ? selectedNode.label : "Daily overview"} for {snapshot.date}
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
      <p className="notice workbench-disclaimer">{snapshot.disclaimer}</p>
    </aside>
  );
}


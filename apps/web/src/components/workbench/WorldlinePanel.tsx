"use client";

import type {
  WorldlineAgentEvent,
  WorldlineDay,
  WorldlineImpactScores,
  WorldlineSimulation,
  WorldlineState,
} from "@/lib/types";
import { formatAgentName } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface WorldlinePanelProps {
  primary?: boolean;
  worldlineDay?: WorldlineDay | null;
  worldlineSimulation?: WorldlineSimulation | null;
}

const IMPACT_SCORE_KEYS: Array<keyof WorldlineImpactScores> = [
  "sentiment_delta",
  "narrative_pressure_delta",
  "leverage_pressure_delta",
  "liquidity_pressure_delta",
  "volatility_pressure_delta",
  "stress_pressure_delta",
];

export function WorldlinePanel({
  primary = false,
  worldlineDay,
  worldlineSimulation,
}: WorldlinePanelProps) {
  const { t } = useI18n();
  if (!worldlineDay) {
    return primary ? (
      <section className="worldline-panel nested-panel">
        <h3>{t("worldline.console")}</h3>
        <p className="muted">{t("worldline.noWorldline")}</p>
      </section>
    ) : null;
  }

  const body = (
    <div className="stack worldline-panel-body">
      {worldlineSimulation ? (
        <WorldlineProvenanceTags simulation={worldlineSimulation} />
      ) : null}

      <section>
        <h3>{t("worldline.whatHappenedToday")}</h3>
        <p>{worldlineDay.input_context_summary}</p>
      </section>

      <section>
        <h3>{t("worldline.pressureUpdate")}</h3>
        <div className="grid">
          <WorldlineStateCard
            label={t("worldline.stateBefore")}
            state={worldlineDay.world_state_before}
          />
          <WorldlineStateCard
            label={t("worldline.stateAfter")}
            state={worldlineDay.world_state_after}
          />
        </div>
      </section>

      <section>
        <h3>{t("worldline.agentEvents")}</h3>
        <div className="stack">
          {worldlineDay.agent_events.map((event) => (
            <AgentEventCard event={event} key={event.agent_id} />
          ))}
        </div>
      </section>

      <section>
        <h3>{t("worldline.causalLinks")}</h3>
        <div className="stack">
          {worldlineDay.causal_links.map((link) => (
            <div
              className="nested-panel"
              key={`${link.source}-${link.target}-${link.strength}`}
            >
              <strong>
                {link.source} → {link.target}
              </strong>
              <p>{link.description}</p>
              <div className="tag-row">
                <span className="tag">{link.strength}</span>
                <span className="tag">{t("worldline.simulatedCause")}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3>{t("worldline.nextDaySetup")}</h3>
        <p>{worldlineDay.next_day_update}</p>
      </section>

      <p className="notice">{worldlineDay.disclaimer}</p>
    </div>
  );

  if (primary) {
    return (
      <section className="worldline-panel nested-panel worldline-panel-primary">
        <div>
          <h3>{t("worldline.console")}</h3>
          <p className="muted">
            {t("worldline.playback")} · {worldlineDay.date}
          </p>
        </div>
        {body}
      </section>
    );
  }

  return (
    <details className="worldline-panel nested-panel">
      <summary>
        <strong>{t("worldline.title")}</strong>
        <span className="muted"> · {worldlineDay.date}</span>
      </summary>
      {body}
    </details>
  );
}

function WorldlineProvenanceTags({
  simulation,
}: {
  simulation: WorldlineSimulation;
}) {
  const { t } = useI18n();
  const provenance = simulation.provenance || {};
  return (
    <div className="tag-row">
      <span className="tag">
        {t("worldline.generationMode")}:{" "}
        {String(provenance.generation_mode || simulation.mode)}
      </span>
      <span className="tag">
        {t("worldline.chunkSize")}:{" "}
        {String(provenance.chunk_size_days || "n/a")}
      </span>
      <span className="tag">
        {t("worldline.chunkStatus")}: {simulation.status}
      </span>
      <span className="tag">
        {t("worldline.failedChunks")}:{" "}
        {String(provenance.failed_chunk_count || 0)}
      </span>
    </div>
  );
}

function WorldlineStateCard({
  label,
  state,
}: {
  label: string;
  state: WorldlineState;
}) {
  const { t } = useI18n();
  return (
    <div className="nested-panel">
      <h3>{label}</h3>
      <div className="tag-row">
        <span className="tag">{state.sentiment_state}</span>
        {state.regime_label ? <span className="tag">{state.regime_label}</span> : null}
      </div>
      <dl className="worldline-score-grid">
        <ScoreTerm label={t("worldline.narrativePressure")} value={state.narrative_pressure} />
        <ScoreTerm label={t("worldline.leveragePressure")} value={state.leverage_pressure} />
        <ScoreTerm label={t("worldline.liquidityPressure")} value={state.liquidity_pressure} />
        <ScoreTerm label={t("worldline.volatilityPressure")} value={state.volatility_pressure} />
        <ScoreTerm label={t("worldline.stressPressure")} value={state.stress_pressure} />
      </dl>
    </div>
  );
}

function ScoreTerm({ label, value }: { label: string; value: number }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value.toFixed(2)}</dd>
    </>
  );
}

function AgentEventCard({ event }: { event: WorldlineAgentEvent }) {
  const { t } = useI18n();
  return (
    <div className="nested-panel">
      <h4>{formatAgentName(t, event.agent_id, event.agent_name)}</h4>
      <div className="grid">
        <div>
          <strong>{t("worldline.whatHappened")}</strong>
          <p>{event.what_happened}</p>
        </div>
        <div>
          <strong>{t("worldline.whyItHappened")}</strong>
          <p>{event.why_it_happened}</p>
        </div>
      </div>
      <div>
        <strong>{t("worldline.impactOnTomorrow")}</strong>
        <p>{event.impact_on_tomorrow}</p>
      </div>
      <details>
        <summary>{t("worldline.impactScores")}</summary>
        <div className="tag-row">
          {IMPACT_SCORE_KEYS.map((key) => (
            <span className="tag" key={key}>
              {key.replaceAll("_", " ")}: {event.impact_scores[key]}
            </span>
          ))}
        </div>
      </details>
    </div>
  );
}

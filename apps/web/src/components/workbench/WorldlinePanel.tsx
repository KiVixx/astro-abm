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
  onRegenerateWorldline?: () => void;
  canRegenerateWorldline?: boolean;
  regenerationActive?: boolean;
  regenerationMessage?: string;
  regenerationError?: string | null;
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
  canRegenerateWorldline = true,
  onRegenerateWorldline,
  primary = false,
  regenerationActive = false,
  regenerationError = null,
  regenerationMessage = "",
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
        <WorldlineReviewHeader
          onRegenerateWorldline={onRegenerateWorldline}
          canRegenerateWorldline={canRegenerateWorldline}
          regenerationActive={regenerationActive}
          regenerationError={regenerationError}
          regenerationMessage={regenerationMessage}
          selectedDay={worldlineDay}
          simulation={worldlineSimulation}
        />
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
        {t("worldline.continuityStatus")}:{" "}
        {simulation.continuity_status === "consistent"
          ? t("worldline.consistent")
          : String(simulation.continuity_status || "legacy_unknown")}
      </span>
      <span className="tag">
        {t("worldline.failedChunks")}:{" "}
        {String(provenance.failed_chunk_count || 0)}
      </span>
    </div>
  );
}

function WorldlineReviewHeader({
  canRegenerateWorldline,
  onRegenerateWorldline,
  regenerationActive,
  regenerationError,
  regenerationMessage,
  selectedDay,
  simulation,
}: {
  canRegenerateWorldline: boolean;
  onRegenerateWorldline?: () => void;
  regenerationActive: boolean;
  regenerationError: string | null;
  regenerationMessage: string;
  selectedDay: WorldlineDay;
  simulation: WorldlineSimulation;
}) {
  const { t } = useI18n();
  const provenance = simulation.provenance || {};
  const failedChunks = numberFromUnknown(provenance.failed_chunk_count);
  const chunkHistory = arrayOfRecords(provenance.chunk_history);
  const qualityNotes = stringArray(provenance.llm_output_quality_notes);
  const sourceCounts = countDaySources(simulation.days);
  return (
    <section className="nested-panel worldline-review-panel">
      <div className="scenario-progress-header">
        <div>
          <h3>{t("worldline.reviewTitle")}</h3>
          <p className="muted">{t("worldline.reviewHelp")}</p>
        </div>
        {onRegenerateWorldline ? (
          <button
            className="button secondary"
            disabled={regenerationActive || !canRegenerateWorldline}
            onClick={onRegenerateWorldline}
            title={!canRegenerateWorldline ? t("worldline.chunkInfoUnavailable") : undefined}
            type="button"
          >
            {regenerationActive
              ? t("worldline.regenerationInProgress")
              : t("worldline.regenerateFromHere")}
          </button>
        ) : null}
      </div>
      {onRegenerateWorldline && !canRegenerateWorldline ? (
        <p className="muted">{t("worldline.chunkInfoUnavailable")}</p>
      ) : null}
      {simulation.last_regeneration ? (
        <p className="muted">
          {t("worldline.regenerationCompleted")}:{" "}
          {String(simulation.last_regeneration.regenerated_at || "unknown")}
        </p>
      ) : null}
      {regenerationMessage ? <p className="muted">{regenerationMessage}</p> : null}
      {regenerationError ? (
        <p className="notice warning">{regenerationError}</p>
      ) : null}
      {failedChunks > 0 ? (
        <p className="notice warning">
          {t("worldline.failedChunkWarning")}: {failedChunks}
        </p>
      ) : null}
      {Boolean(provenance.generation_halted) ? (
        <p className="notice warning">
          <strong>{t("worldline.generationHalted")}</strong>
          <br />
          {t("worldline.generationHaltedReason")}
        </p>
      ) : null}
      <WorldlineProvenanceTags simulation={simulation} />
      <div className="tag-row">
        {Object.entries(sourceCounts).map(([source, count]) => (
          <span className="tag" key={source}>
            {t("worldline.daysFrom")} {source}: {count}
          </span>
        ))}
      </div>
      <div className="tag-row">
        <span className="tag">
          {t("worldline.selectedDaySource")}: {selectedDay.generation_source || "unknown"}
        </span>
        {selectedDay.chunk_index ? (
          <span className="tag">
            {t("worldline.chunkIndex")}: {selectedDay.chunk_index}
          </span>
        ) : null}
        {selectedDay.chunk_status ? (
          <span className="tag">
            {t("worldline.chunkStatus")}: {selectedDay.chunk_status}
          </span>
        ) : null}
        {provenance.attempt_count ? (
          <span className="tag">
            {t("worldline.attemptCount")}: {String(provenance.attempt_count)}/
            {String(provenance.max_attempts || "3")}
          </span>
        ) : null}
      </div>
      {chunkHistory.length ? (
        <details>
          <summary>{t("worldline.chunkProvenance")}</summary>
          <div className="stack">
            {chunkHistory.map((chunk, index) => (
              <div className="tag-row" key={`${chunk.chunk_index || index}-${chunk.chunk_start_date || ""}`}>
                <span className="tag">
                  #{String(chunk.chunk_index || index + 1)}
                </span>
                <span className="tag">
                  {String(chunk.chunk_start_date || "?")} → {String(chunk.chunk_end_date || "?")}
                </span>
                <span className="tag">{String(chunk.status || "unknown")}</span>
                <span className="tag">
                  {String(chunk.output_validation_status || "unknown")}
                </span>
                <span className="tag">
                  {String(chunk.safety_check_status || "unknown")}
                </span>
                <span className="tag">
                  {t("worldline.attemptCount")}: {String(chunk.attempt_count || "n/a")}/
                  {String(chunk.max_attempts || "3")}
                </span>
              </div>
            ))}
          </div>
        </details>
      ) : null}
      <details>
        <summary>{t("worldline.qualityNotes")}</summary>
        <ul>
          {[...qualityNotes, ...(selectedDay.quality_notes || [])].length ? (
            [...qualityNotes, ...(selectedDay.quality_notes || [])].map((note, index) => (
              <li key={`${note}-${index}`}>{note}</li>
            ))
          ) : (
            <li>{t("worldline.noQualityNotes")}</li>
          )}
        </ul>
      </details>
    </section>
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

function numberFromUnknown(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function arrayOfRecords(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is Record<string, unknown> =>
      typeof item === "object" && item !== null && !Array.isArray(item),
  );
}

function countDaySources(days: WorldlineDay[]): Record<string, number> {
  return days.reduce<Record<string, number>>((counts, day) => {
    const source = day.generation_source || "unknown";
    counts[source] = (counts[source] || 0) + 1;
    return counts;
  }, {});
}

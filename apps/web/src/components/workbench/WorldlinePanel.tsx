"use client";

import type {
  WorldlineAgentEvent,
  WorldlineDay,
  WorldlineImpactScores,
  WorldlineSimulation,
  WorldlineState,
} from "@/lib/types";
import { worldlineGenerationMode } from "@/lib/worldline";
import { formatAgentName } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";
import {
  worldlineDisplayStatus,
  worldlineFallbackBreakdown,
} from "@/lib/worldlineStatus";

interface WorldlinePanelProps {
  primary?: boolean;
  onRegenerateWorldline?: () => void;
  canRegenerateWorldline?: boolean;
  resumeRegeneration?: boolean;
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
  resumeRegeneration = false,
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
          resumeRegeneration={resumeRegeneration}
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
        {worldlineGenerationMode(simulation)}
      </span>
      <span className="tag">
        {t("worldline.chunkSize")}:{" "}
        {String(provenance.chunk_size_days || "n/a")}
      </span>
      <span className="tag">
        {t("worldline.chunkStatus")}: {worldlineDisplayStatus(simulation)}
      </span>
      <span className="tag">
        {t("worldline.continuityStatus")}:{" "}
        {simulation.continuity_status === "consistent"
          ? t("worldline.consistent")
          : simulation.continuity_status === "rebuilding"
            ? t("worldline.rebuilding")
          : String(simulation.continuity_status || "legacy_unknown")}
      </span>
      <span className="tag">
        {t("worldline.failedChunks")}:{" "}
        {String(provenance.failed_chunk_count || 0)}
      </span>
      {numberFromUnknown(provenance.skipped_chunk_count) > 0 ? (
        <span className="tag">
          {t("worldline.skippedChunks")}: {String(provenance.skipped_chunk_count)}
        </span>
      ) : null}
    </div>
  );
}

function WorldlineReviewHeader({
  canRegenerateWorldline,
  resumeRegeneration,
  onRegenerateWorldline,
  regenerationActive,
  regenerationError,
  regenerationMessage,
  selectedDay,
  simulation,
}: {
  canRegenerateWorldline: boolean;
  resumeRegeneration: boolean;
  onRegenerateWorldline?: () => void;
  regenerationActive: boolean;
  regenerationError: string | null;
  regenerationMessage: string;
  selectedDay: WorldlineDay;
  simulation: WorldlineSimulation;
}) {
  const { t } = useI18n();
  const provenance = simulation.provenance || {};
  const fallbackBreakdown = worldlineFallbackBreakdown(simulation);
  const failedChunks = fallbackBreakdown.llmFailed;
  const chunkHistory = arrayOfRecords(provenance.chunk_history);
  const regeneration = regenerationOutcome(simulation.last_regeneration, chunkHistory);
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
              : resumeRegeneration
                ? t("worldline.resumeInterruptedRegeneration")
                : t("worldline.regenerateFromHere")}
          </button>
        ) : null}
      </div>
      {onRegenerateWorldline && !canRegenerateWorldline ? (
        <p className="muted">{t("worldline.chunkInfoUnavailable")}</p>
      ) : null}
      {resumeRegeneration ? (
        <p className="notice warning">{t("worldline.interruptedRegenerationDetected")}</p>
      ) : null}
      {simulation.last_regeneration ? (
        <div
          className={
            regeneration.status === "completed"
              || regeneration.status === "configuration_fallback"
              ? "notice"
              : "notice warning"
          }
        >
          <strong>
            {regeneration.status === "completed"
              ? t("worldline.regenerationSucceeded")
              : regeneration.status === "configuration_fallback"
                ? t("worldline.regenerationConfigurationFallback")
              : regeneration.status === "partial_fallback"
                ? t("worldline.regenerationPartialFallback")
                : t("worldline.regenerationFailedFallback")}
          </strong>
          <p>
            {t("worldline.regenerationEndedAt")}: {" "}
            {String(simulation.last_regeneration.regenerated_at || "unknown")}
          </p>
          <p>
            {t("worldline.llmCompletedChunks")}: {regeneration.completed} · {" "}
            {t("worldline.fallbackChunks")}: {regeneration.fallback} · {" "}
            {t("worldline.skippedChunks")}: {regeneration.skipped}
          </p>
          {regeneration.error ? (
            <p>
              {regeneration.status === "configuration_fallback"
                ? t("worldline.configurationFallbackReason")
                : t("worldline.failureReason")}: {regeneration.error}
            </p>
          ) : null}
        </div>
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
      {fallbackBreakdown.configurationFallback > 0 ? (
        <div className="notice">
          <strong>
            {t("worldline.configurationFallbackChunks")}: {fallbackBreakdown.configurationFallback}
          </strong>
          <p>{t("worldline.configurationFallbackHelp")}</p>
          <div className="tag-row">
            {Object.entries(fallbackBreakdown.reasonCounts).map(([reason, count]) => (
              <span className="tag" key={reason}>
                {t(`worldline.failureKind.${reason}`, reason)}: {count}
              </span>
            ))}
          </div>
        </div>
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
              <div className="stack" key={`${chunk.chunk_index || index}-${chunk.chunk_start_date || ""}`}>
                <div className="tag-row">
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
                <ChunkAttemptHistory value={chunk.attempt_history} />
                <ChunkRequestDiagnostics value={chunk.request_diagnostics} />
                <ChunkResponseDiagnostics value={chunk.response_diagnostics} />
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

function ChunkAttemptHistory({ value }: { value: unknown }) {
  const { t } = useI18n();
  if (!Array.isArray(value) || value.length === 0) {
    return null;
  }
  const attempts = value.map(recordFromUnknown).filter((item) => item !== null);
  if (!attempts.length) {
    return null;
  }
  return (
    <details>
      <summary>{t("worldline.attemptHistory")}</summary>
      <div className="stack">
        {attempts.map((attempt, index) => (
          <div className="nested-panel" key={`${String(attempt.attempt || index + 1)}-${index}`}>
            <div className="tag-row">
              <span className="tag">
                {t("worldline.attemptLabel")} {String(attempt.attempt || index + 1)}
              </span>
              <span className="tag">
                {String(attempt.output_validation_status || "unknown")}
              </span>
              <span className="tag">{String(attempt.safety_check_status || "unknown")}</span>
            </div>
            {Array.isArray(attempt.safety_violation_codes) && attempt.safety_violation_codes.length ? (
              <p className="notice warning">
                <strong>{t("worldline.safetyRuleCategories")}:</strong>{" "}
                {attempt.safety_violation_codes.map(String).join(", ")}
              </p>
            ) : null}
            {attempt.reason ? <p className="muted">{String(attempt.reason)}</p> : null}
            <ChunkRequestDiagnostics value={attempt.request_diagnostics} />
            <ChunkResponseDiagnostics value={attempt.response_diagnostics} />
          </div>
        ))}
      </div>
    </details>
  );
}

function ChunkRequestDiagnostics({ value }: { value: unknown }) {
  const { t } = useI18n();
  const diagnostics = recordFromUnknown(value);
  if (!diagnostics || !diagnostics.error_category) {
    return null;
  }
  const failureKind = diagnostics.failure_kind
    ? String(diagnostics.failure_kind)
    : String(diagnostics.error_category);
  const recommendedAction = diagnostics.recommended_action
    ? String(diagnostics.recommended_action)
    : null;
  return (
    <details>
      <summary>{t("worldline.requestDiagnostics")}</summary>
      <div className="tag-row">
        <span className="tag">
          {t("worldline.errorCategory")}: {String(diagnostics.error_category)}
        </span>
        <span className="tag">
          {t("worldline.failureKind")}: {t(`worldline.failureKind.${failureKind}`, failureKind)}
        </span>
        <span className="tag">
          {t("worldline.retryable")}: {diagnostics.retryable === true ? "true" : "false"}
        </span>
        {diagnostics.http_status ? (
          <span className="tag">
            {t("worldline.httpStatus")}: {String(diagnostics.http_status)}
          </span>
        ) : null}
      </div>
      {recommendedAction ? (
        <p className="notice warning">
          <strong>{t("worldline.recommendedAction")}:</strong>{" "}
          {t(`worldline.requestAction.${recommendedAction}`, recommendedAction)}
        </p>
      ) : null}
      <p className="muted">{t("worldline.requestDiagnosticsPrivacyNote")}</p>
    </details>
  );
}

function ChunkResponseDiagnostics({ value }: { value: unknown }) {
  const { t } = useI18n();
  const diagnostics = recordFromUnknown(value);
  if (!diagnostics || diagnostics.response_char_count === undefined) {
    return null;
  }
  const errorLine = numberFromUnknown(diagnostics.parse_error_line);
  const errorColumn = numberFromUnknown(diagnostics.parse_error_column);
  const parseErrorType = diagnostics.parse_error_type
    ? String(diagnostics.parse_error_type)
    : t("worldline.noParseError");
  return (
    <details>
      <summary>{t("worldline.responseDiagnostics")}</summary>
      <div className="tag-row">
        <span className="tag">
          {t("worldline.responseLength")}: {String(diagnostics.response_char_count)} {t("worldline.characters")}
        </span>
        <span className="tag">
          {t("worldline.parseResult")}: {parseErrorType}
        </span>
        {errorLine > 0 && errorColumn > 0 ? (
          <span className="tag">
            {t("worldline.errorLocation")}: {errorLine}:{errorColumn}
          </span>
        ) : null}
        {diagnostics.markdown_fence_detected === true ? (
          <span className="tag">{t("worldline.markdownFenceDetected")}</span>
        ) : null}
        {diagnostics.leading_text_ignored === true ? (
          <span className="tag">{t("worldline.leadingTextIgnored")}</span>
        ) : null}
        {diagnostics.trailing_text_ignored === true ? (
          <span className="tag">{t("worldline.trailingTextIgnored")}</span>
        ) : null}
      </div>
      {diagnostics.probable_truncation === true ? (
        <p className="notice warning">
          <strong>{t("worldline.probableTruncation")}</strong>
          <br />
          {t("worldline.probableTruncationHelp")}
        </p>
      ) : null}
      <p className="muted">{t("worldline.diagnosticsPrivacyNote")}</p>
    </details>
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

function recordFromUnknown(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function countDaySources(days: WorldlineDay[]): Record<string, number> {
  return days.reduce<Record<string, number>>((counts, day) => {
    const source = day.generation_source || "unknown";
    counts[source] = (counts[source] || 0) + 1;
    return counts;
  }, {});
}

function regenerationOutcome(
  lastRegeneration: Record<string, unknown> | null | undefined,
  chunkHistory: Array<Record<string, unknown>>,
) {
  if (!lastRegeneration) {
    return { status: "completed", completed: 0, fallback: 0, skipped: 0, error: "" };
  }
  const regeneratedAt = String(lastRegeneration.regenerated_at || "");
  const relevant = chunkHistory.filter(
    (chunk) => regeneratedAt && String(chunk.regenerated_at || "") === regeneratedAt,
  );
  const completed = numberFromUnknown(lastRegeneration.llm_completed_chunk_count)
    || relevant.filter((chunk) => chunk.status === "completed").length;
  const fallback = numberFromUnknown(lastRegeneration.fallback_chunk_count)
    || relevant.filter((chunk) => chunk.status === "fallback").length;
  const skipped = numberFromUnknown(lastRegeneration.skipped_chunk_count)
    || relevant.filter((chunk) => chunk.status === "skipped_after_halt").length;
  const storedStatus = String(lastRegeneration.status || "");
  const status = storedStatus || (
    fallback + skipped === 0
      ? "completed"
      : completed > 0
        ? "partial_fallback"
        : "failed_fallback"
  );
  const firstIssue = relevant
    .flatMap((chunk) => stringArray(chunk.issues))
    .find((issue) => !issue.startsWith("LLM regeneration failed safely"));
  return {
    status,
    completed,
    fallback,
    skipped,
    error: String(lastRegeneration.error_summary || firstIssue || ""),
  };
}

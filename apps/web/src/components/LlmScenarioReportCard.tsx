"use client";

import type { LlmScenarioReport } from "@/lib/types";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

function BulletList({ items }: { items: string[] }) {
  const { t } = useI18n();
  if (!items.length) {
    return <p className="muted">{t("coverage.noEntries")}</p>;
  }
  return (
    <ul>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function LlmScenarioReportCard({
  compact = false,
  llmReport,
}: {
  compact?: boolean;
  llmReport?: LlmScenarioReport | null;
}) {
  const { t } = useI18n();
  if (!llmReport) {
    return (
      <section className={compact ? "nested-panel" : "card"}>
        <h2>{t("llm.title")}</h2>
        <p className="muted">{t("llm.missing")}</p>
      </section>
    );
  }

  return (
    <section className={compact ? "nested-panel stack" : "card stack"}>
      <div>
        <h2>{t("llm.title")}</h2>
        <div className="tag-row">
          <span className="tag">
            {t("llm.status")}: {formatEnumLabel(t, "llm_status", llmReport.status)}
          </span>
          <span className="tag">
            {t("llm.provider")}:{" "}
            {formatEnumLabel(t, "llm_provider", llmReport.provider)}
          </span>
          <span className="tag">
            {t("llm.model")}: {llmReport.model || t("value.common.unknown")}
          </span>
          <span className="tag">
            {t("llm.networkCallPerformed")}:{" "}
            {llmReport.provenance.network_call_performed ? "true" : "false"}
          </span>
        </div>
      </div>

      {llmReport.status === "completed" ? (
        <>
          <div>
            <h3>{t("llm.executiveSummary")}</h3>
            <p>{llmReport.executive_summary}</p>
          </div>
          <div>
            <h3>{t("llm.scenarioReading")}</h3>
            <p>{llmReport.scenario_reading}</p>
          </div>
          {!compact ? (
            <>
              <div>
                <h3>{t("llm.dailyHighlights")}</h3>
                <div className="stack">
                  {llmReport.daily_highlights.map((highlight) => (
                    <div className="nested-panel" key={highlight.date}>
                      <strong>{highlight.date}</strong>
                      <p>{highlight.summary}</p>
                      <div className="grid">
                        <div>
                          <h4>{t("llm.keyContext")}</h4>
                          <BulletList items={highlight.key_context} />
                        </div>
                        <div>
                          <h4>{t("llm.agentFocus")}</h4>
                          <BulletList items={highlight.agent_focus} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h3>{t("llm.agentInterpretations")}</h3>
                <div className="stack">
                  {llmReport.agent_interpretations.map((agent) => (
                    <div className="nested-panel" key={agent.agent_id}>
                      <strong>
                        {formatAgentName(t, agent.agent_id, agent.agent_name)}
                      </strong>
                      <p>{agent.interpretation}</p>
                      <BulletList items={agent.risk_focus} />
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
          <div className="grid">
            <div>
              <h3>{t("llm.riskThemes")}</h3>
              <BulletList items={llmReport.risk_themes} />
            </div>
            <div>
              <h3>{t("llm.caveats")}</h3>
              <BulletList items={llmReport.caveats} />
            </div>
          </div>
        </>
      ) : (
        <div className="notice">
          <h3>
            {llmReport.status === "dry_run"
              ? t("llm.dryRun")
              : formatEnumLabel(t, "llm_status", llmReport.status)}
          </h3>
          <p>{llmReport.executive_summary}</p>
          <p>{llmReport.scenario_reading}</p>
        </div>
      )}

      <details>
        <summary>{t("llm.provenance")}</summary>
        <div className="tag-row">
          <span className="tag">
            {t("llm.outputValidation")}:{" "}
            {llmReport.provenance.output_validation_status}
          </span>
          <span className="tag">
            {t("llm.safetyCheck")}: {llmReport.provenance.safety_check_status}
          </span>
          <span className="tag">
            {t("llm.promptTemplate")}:{" "}
            {llmReport.provenance.prompt_template_version}
          </span>
          <span className="tag">
            {t("llm.credentialStatus")}:{" "}
            {llmReport.provenance.credential_status}
          </span>
        </div>
      </details>
      <p className="notice">{llmReport.disclaimer}</p>
    </section>
  );
}

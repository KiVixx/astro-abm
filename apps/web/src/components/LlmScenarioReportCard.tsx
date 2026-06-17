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

function ScenarioReadingText({ text }: { text: string }) {
  const blocks = normalizeScenarioReadingText(text)
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  if (!blocks.length) {
    return <p className="muted">-</p>;
  }

  return (
    <div className="llm-readable-text">
      {blocks.map((block, blockIndex) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        if (lines.length === 1) {
          const heading = parseMarkdownHeading(lines[0]);
          if (heading) {
            return <h4 key={`${blockIndex}-${heading}`}>{heading}</h4>;
          }
          return <p key={`${blockIndex}-${lines[0]}`}>{lines[0]}</p>;
        }
        return (
          <div className="llm-readable-block" key={`${blockIndex}-${lines[0]}`}>
            {lines.map((line, lineIndex) => {
              const heading = parseMarkdownHeading(line);
              if (heading) {
                return <h4 key={`${lineIndex}-${heading}`}>{heading}</h4>;
              }
              const bullet = parseMarkdownBullet(line);
              if (bullet) {
                return <p className="llm-readable-bullet" key={`${lineIndex}-${bullet}`}>{bullet}</p>;
              }
              return <p key={`${lineIndex}-${line}`}>{line}</p>;
            })}
          </div>
        );
      })}
    </div>
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

  const containerClass = compact
    ? "nested-panel stack llm-report-card"
    : "card stack llm-report-card";

  return (
    <details className={containerClass}>
      <summary className="llm-report-summary">
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
      </summary>

      <div className="llm-report-body stack">
        {llmReport.status === "completed" ? (
          <>
          <div>
            <h3>{t("llm.executiveSummary")}</h3>
            <p>{llmReport.executive_summary}</p>
          </div>
          <div>
            <h3>{t("llm.scenarioReading")}</h3>
            <ScenarioReadingText text={llmReport.scenario_reading} />
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
              <div>
                <h3>{t("llm.assetStressIndicators")}</h3>
                <div className="stack">
                  {(llmReport.asset_stress_indicators || []).slice(0, 12).map((indicator) => (
                    <div
                      className="nested-panel"
                      key={`${indicator.date}-${indicator.asset}`}
                    >
                      <strong>
                        {indicator.date} · {indicator.asset} ·{" "}
                        {indicator.sentiment_stress_support.toFixed(1)}
                      </strong>
                      <p>{indicator.rationale}</p>
                      <div className="tag-row">
                        <span className="tag">{indicator.label}</span>
                        <span className="tag">{t("workbench.llmMetric")}</span>
                      </div>
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
          <ScenarioReadingText text={llmReport.scenario_reading} />
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
      </div>
    </details>
  );
}

function normalizeScenarioReadingText(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed.includes("\n") || trimmed.length < 600) {
    return trimmed;
  }
  return trimmed
    .replace(/。\s+(?=(?:\d{4}[年-]|在\d{4}年|單日快照|此單日快照|當日|當前情境|壓力平穩|202\d))/g, "。\n\n")
    .replace(/\s+(?=(?:\d{4}-\d{2}-\d{2}|202\d年\d{1,2}月\d{1,2}日))/g, "\n\n");
}

function parseMarkdownHeading(line: string): string | null {
  const match = line.match(/^#{1,6}\s+(.+)$/);
  return match?.[1]?.trim() || null;
}

function parseMarkdownBullet(line: string): string | null {
  const match = line.match(/^[-*]\s+(.+)$/);
  return match?.[1]?.trim() || null;
}

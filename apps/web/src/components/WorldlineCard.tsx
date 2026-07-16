"use client";

import Link from "next/link";
import type { ScenarioSummary } from "@/lib/types";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

export function WorldlineCard({
  isDeleting = false,
  onDelete,
  report,
}: {
  isDeleting?: boolean;
  onDelete?: (report: ScenarioSummary) => void;
  report: ScenarioSummary;
}) {
  const { t } = useI18n();
  const generationMode = report.worldline_generation_mode || "";
  const generationModeLabel = generationMode.includes("llm_chunk")
    ? t("worldline.llmChunk")
    : generationMode.includes("deterministic")
      ? t("worldline.deterministicMock")
      : generationMode || t("worldline.noWorldlineShort");
  const status = report.worldline_status || "legacy";
  const statusTone = ["failed", "fallback"].includes(status)
    ? "alert"
    : ["completed", "mock_completed"].includes(status)
      ? "ready"
      : "legacy";
  const visibleAssets = report.assets.slice(0, 6);
  const visibleAgents = report.agent_names.slice(0, 4);

  return (
    <article className="worldline-record" data-status={statusTone}>
      <div className="worldline-record-main">
        <div className="worldline-record-heading">
          <div>
            <p className="worldline-record-id">ID // {report.scenario_id}</p>
            <h3>
              <Link href={`/worldlines/${report.scenario_id}`}>{report.title}</Link>
            </h3>
          </div>
          <p className="worldline-record-date">
            {report.start_date} {t("common.to")} {report.end_date} ·{" "}
            {t("common.created")}: {report.created_at.slice(0, 10)}
          </p>
        </div>

        <div className="worldline-record-signals">
          <span className="worldline-status-signal">
            <i aria-hidden="true" />
            {t("worldline.status")}: {status}
          </span>
          <span>{t("worldline.mode")}: {generationModeLabel}</span>
          <span>{t("worldline.dayCount")}: {report.worldline_day_count || 0}</span>
          {Number(report.worldline_llm_failed_chunk_count || 0) > 0 ? (
            <span className="worldline-record-warning">
              {t("worldline.failedChunks")}: {report.worldline_llm_failed_chunk_count}
            </span>
          ) : null}
          {Number(report.worldline_configuration_fallback_chunk_count || 0) > 0 ? (
            <span className="worldline-record-warning">
              {t("worldline.configurationFallbackChunks")}: {report.worldline_configuration_fallback_chunk_count}
            </span>
          ) : null}
          {report.llm_report_status ? (
            <span>{t("llm.title")}: {formatEnumLabel(t, "llm_status", report.llm_report_status)}</span>
          ) : null}
        </div>
      </div>

      <div className="worldline-record-context">
        <div>
          <span className="worldline-record-label">{t("worldline.marketSeries")}</span>
          <div className="tag-row">
            {visibleAssets.map((asset) => <span className="tag" key={asset}>{asset}</span>)}
            {report.assets.length > visibleAssets.length ? (
              <span className="tag">+{report.assets.length - visibleAssets.length}</span>
            ) : null}
          </div>
        </div>
        <div>
          <span className="worldline-record-label">{t("worldline.agentGroupsLabel")}</span>
          <div className="tag-row">
            {visibleAgents.map((agentName, index) => (
              <span className="tag" key={report.agent_ids[index] || agentName}>
                {formatAgentName(t, report.agent_ids[index] || "", agentName)}
              </span>
            ))}
            {report.agent_names.length > visibleAgents.length ? (
              <span className="tag">+{report.agent_names.length - visibleAgents.length}</span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="worldline-record-footer">
        <p>
          {report.coverage_total_days !== null && report.coverage_total_days !== undefined ? (
            <>
              {t("coverage.localResearchDays")}: {report.coverage_local_research_days || 0} ·{" "}
              {t("coverage.futurePlaceholderDays")}: {report.coverage_future_placeholder_days || 0}
            </>
          ) : t("coverage.legacyMissing")}
        </p>
        <div className="worldline-record-actions">
          <Link className="button" href={`/worldlines/${report.scenario_id}`}>
            {t("worldline.openWorldline")}
          </Link>
          <Link className="button secondary" href={`/scenarios/${report.scenario_id}/report`}>
            {t("worldline.openReport")}
          </Link>
          {onDelete ? (
            <button
              className="button danger"
              disabled={isDeleting}
              onClick={() => onDelete(report)}
              type="button"
            >
              {isDeleting ? t("scenarios.deleting") : t("scenarios.delete")}
            </button>
          ) : null}
        </div>
      </div>
    </article>
  );
}

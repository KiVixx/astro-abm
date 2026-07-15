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

  return (
    <article className="card worldline-card">
      <div className="scenario-card-header">
        <div>
          <h3>{report.title}</h3>
          <p className="muted">
            {report.start_date} {t("common.to")} {report.end_date} ·{" "}
            {t("common.created")}: {report.created_at.slice(0, 10)}
          </p>
        </div>
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

      <div className="tag-row">
        <span className="tag">
          {t("worldline.status")}:{" "}
          {report.worldline_status || t("worldline.noWorldlineShort")}
        </span>
        <span className="tag">
          {t("worldline.mode")}:{" "}
          {report.worldline_generation_mode || t("worldline.noWorldlineShort")}
        </span>
        <span className="tag">
          {t("worldline.dayCount")}: {report.worldline_day_count || 0}
        </span>
        <span className="tag">
          {t("llm.status")}:{" "}
          {report.llm_report_status
            ? formatEnumLabel(t, "llm_status", report.llm_report_status)
            : t("llm.missing")}
        </span>
        {Number(report.worldline_configuration_fallback_chunk_count || 0) > 0 ? (
          <span className="tag">
            {t("worldline.configurationFallbackChunks")}:{" "}
            {report.worldline_configuration_fallback_chunk_count}
          </span>
        ) : null}
        {Number(report.worldline_llm_failed_chunk_count || 0) > 0 ? (
          <span className="tag">
            {t("worldline.failedChunks")}: {report.worldline_llm_failed_chunk_count}
          </span>
        ) : null}
      </div>

      <div className="tag-row">
        {report.assets.map((asset) => (
          <span className="tag" key={asset}>
            {asset}
          </span>
        ))}
        {report.agent_names.map((agentName, index) => (
          <span className="tag" key={report.agent_ids[index] || agentName}>
            {formatAgentName(t, report.agent_ids[index] || "", agentName)}
          </span>
        ))}
      </div>

      {report.coverage_total_days !== null && report.coverage_total_days !== undefined ? (
        <p className="muted">
          {t("coverage.totalDays")}: {report.coverage_total_days};{" "}
          {t("coverage.localResearchDays")}:{" "}
          {report.coverage_local_research_days || 0};{" "}
          {t("coverage.futurePlaceholderDays")}:{" "}
          {report.coverage_future_placeholder_days || 0}
        </p>
      ) : null}

      <div className="button-row">
        <Link className="button" href={`/worldlines/${report.scenario_id}`}>
          {t("worldline.openWorldline")}
        </Link>
        <Link className="button secondary" href={`/scenarios/${report.scenario_id}/report`}>
          {t("worldline.openReport")}
        </Link>
      </div>
    </article>
  );
}

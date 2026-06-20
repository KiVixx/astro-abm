"use client";

import Link from "next/link";
import type { ScenarioReport } from "@/lib/types";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

export function WorldlineCard({
  isDeleting = false,
  onDelete,
  report,
}: {
  isDeleting?: boolean;
  onDelete?: (report: ScenarioReport) => void;
  report: ScenarioReport;
}) {
  const { t } = useI18n();
  const worldline = report.worldline_simulation;

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
          {worldline ? worldline.status : t("worldline.noWorldlineShort")}
        </span>
        <span className="tag">
          {t("worldline.mode")}:{" "}
          {worldline?.mode || t("worldline.noWorldlineShort")}
        </span>
        <span className="tag">
          {t("worldline.dayCount")}: {worldline?.horizon_days || 0}
        </span>
        <span className="tag">
          {t("llm.status")}:{" "}
          {report.llm_report
            ? formatEnumLabel(t, "llm_status", report.llm_report.status)
            : t("llm.missing")}
        </span>
      </div>

      <div className="tag-row">
        {report.assets.map((asset) => (
          <span className="tag" key={asset}>
            {asset}
          </span>
        ))}
        {report.agents.map((agent) => (
          <span className="tag" key={agent.agent_id}>
            {formatAgentName(t, agent.agent_id, agent.name)}
          </span>
        ))}
      </div>

      {report.coverage_summary ? (
        <p className="muted">
          {t("coverage.totalDays")}: {report.coverage_summary.total_days};{" "}
          {t("coverage.localResearchDays")}:{" "}
          {report.coverage_summary.local_research_days};{" "}
          {t("coverage.futurePlaceholderDays")}:{" "}
          {report.coverage_summary.future_placeholder_days}
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

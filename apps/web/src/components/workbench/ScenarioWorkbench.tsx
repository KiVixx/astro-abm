"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ContextCoverageSummaryCard } from "../ContextCoverageSummaryCard";
import { LlmScenarioReportCard } from "../LlmScenarioReportCard";
import { DailyGraphCanvas } from "./DailyGraphCanvas";
import { DailyTimelineRail } from "./DailyTimelineRail";
import { WorkbenchPanel } from "./WorkbenchPanel";
import type { DailyScenarioSnapshot, ScenarioReport } from "@/lib/types";
import { buildAssetStressSeries } from "@/lib/assetStressSentiment";
import { buildWorkbenchGraph } from "@/lib/workbenchGraph";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface ScenarioWorkbenchProps {
  report: ScenarioReport;
  initialDate?: string;
  product?: "scenario" | "worldline";
}

function getInitialSnapshot(
  timeline: DailyScenarioSnapshot[],
  initialDate?: string,
): DailyScenarioSnapshot | null {
  if (!timeline.length) {
    return null;
  }
  if (initialDate) {
    return timeline.find((snapshot) => snapshot.date === initialDate) || timeline[0];
  }
  return timeline[0];
}

export function ScenarioWorkbench({
  report,
  initialDate,
  product = "scenario",
}: ScenarioWorkbenchProps) {
  const { t } = useI18n();
  const isWorldline = product === "worldline";
  const timeline = report.daily_timeline || [];
  const initialSnapshot = getInitialSnapshot(timeline, initialDate);
  const [selectedDate, setSelectedDate] = useState(initialSnapshot?.date || "");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const selectedSnapshot =
    timeline.find((snapshot) => snapshot.date === selectedDate) || initialSnapshot;
  const selectedIndex = selectedSnapshot
    ? timeline.findIndex((snapshot) => snapshot.date === selectedSnapshot.date)
    : -1;
  const previousSnapshot = selectedIndex > 0 ? timeline[selectedIndex - 1] : undefined;
  const nextSnapshot =
    selectedIndex >= 0 && selectedIndex < timeline.length - 1
      ? timeline[selectedIndex + 1]
      : undefined;

  const graph = useMemo(() => {
    return selectedSnapshot ? buildWorkbenchGraph(report, selectedSnapshot) : null;
  }, [report, selectedSnapshot]);
  const assetStressSeries = useMemo(
    () => buildAssetStressSeries(report, timeline),
    [report, timeline],
  );

  const selectedNode =
    graph?.nodes.find((node) => node.id === selectedNodeId) || null;
  const selectedEdge =
    graph?.edges.find((edge) => edge.id === selectedEdgeId) || null;
  const selectedWorldlineDay =
    report.worldline_simulation?.days.find(
      (day) => day.date === selectedSnapshot?.date,
    ) || null;

  const selectDate = (date: string) => {
    setSelectedDate(date);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  };

  if (!selectedSnapshot || !graph) {
    return (
      <div className="page stack">
        <Link
          className="button secondary"
          href={`/scenarios/${report.scenario_id}/report`}
        >
          {isWorldline ? t("worldline.openReport") : t("workbench.openReport")}
        </Link>
        {isWorldline ? (
          <Link className="button secondary" href="/worldlines">
            {t("worldline.backToWorldlines")}
          </Link>
        ) : null}
        <section className="notice">
          <h1>{isWorldline ? t("worldline.workbench") : t("workbench.noTimelineTitle")}</h1>
          <p>
            {isWorldline ? t("worldline.noWorldline") : t("workbench.noTimeline")}
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="workbench-page">
      <header className="workbench-header">
        <div>
          <p className="muted">
            {isWorldline ? t("worldline.workbench") : t("workbench.productName")}
          </p>
          <h1>{report.title}</h1>
          <div className="tag-row">
            <span className="tag">{selectedSnapshot.date}</span>
            {isWorldline && report.worldline_simulation ? (
              <>
                <span className="tag">
                  {t("worldline.status")}: {report.worldline_simulation.status}
                </span>
                <span className="tag">
                  {t("worldline.dayCount")}: {selectedIndex + 1}/
                  {report.worldline_simulation.horizon_days}
                </span>
              </>
            ) : null}
            <span className="tag">
              {report.start_date} {t("common.to")} {report.end_date}
            </span>
            <span className="tag">
              {formatEnumLabel(t, "scenario_mode", report.mode)}
            </span>
            <span className="tag">
              {t("report.generatedLanguage")}:{" "}
              {formatEnumLabel(t, "report_language", report.language || "legacy")}
            </span>
          </div>
        </div>
        <div className="button-row">
          <Link
            className="button secondary"
            href={`/scenarios/${report.scenario_id}/report`}
          >
            {t("worldline.openReport")}
          </Link>
          <Link className="button secondary" href={isWorldline ? "/worldlines" : "/scenarios"}>
            {isWorldline ? t("worldline.backToWorldlines") : t("common.scenarioList")}
          </Link>
        </div>
      </header>

      <ContextCoverageSummaryCard
        compact
        coverageSummary={report.coverage_summary}
      />

      {!isWorldline ? <LlmScenarioReportCard compact llmReport={report.llm_report} /> : null}

      {isWorldline ? (
        <section className="worldline-playback-bar">
          <strong>{t("worldline.playback")}</strong>
          <button
            className="button secondary"
            disabled={!previousSnapshot}
            onClick={() => previousSnapshot && selectDate(previousSnapshot.date)}
            type="button"
          >
            {t("workbench.previous")}
          </button>
          <span className="tag">{selectedSnapshot.date}</span>
          <span className="tag">
            {selectedIndex + 1}/{timeline.length}
          </span>
          <button
            className="button secondary"
            disabled={!nextSnapshot}
            onClick={() => nextSnapshot && selectDate(nextSnapshot.date)}
            type="button"
          >
            {t("workbench.next")}
          </button>
        </section>
      ) : null}

      <DailyTimelineRail
        assetStressSeries={assetStressSeries}
        onSelectDate={selectDate}
        selectedDate={selectedSnapshot.date}
        timeline={timeline}
      />

      <main className="workbench-layout">
        <DailyGraphCanvas
          graph={graph}
          nextDate={nextSnapshot?.date}
          onSelectDate={selectDate}
          onSelectEdge={setSelectedEdgeId}
          onSelectNode={setSelectedNodeId}
          previousDate={previousSnapshot?.date}
          selectedDate={selectedSnapshot.date}
          selectedEdgeId={selectedEdgeId}
          selectedNodeId={selectedNodeId}
        />
        <WorkbenchPanel
          graph={graph}
          selectedEdge={selectedEdge}
          selectedNode={selectedNode}
          snapshot={selectedSnapshot}
          worldlineDay={selectedWorldlineDay}
          worldlineSimulation={report.worldline_simulation}
          worldlinePrimary={isWorldline}
        />
      </main>
    </div>
  );
}

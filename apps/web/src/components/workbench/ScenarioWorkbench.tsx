"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { DailyGraphCanvas } from "./DailyGraphCanvas";
import { DailyTimelineRail } from "./DailyTimelineRail";
import { WorkbenchPanel } from "./WorkbenchPanel";
import type { DailyScenarioSnapshot, ScenarioReport } from "@/lib/types";
import { buildWorkbenchGraph } from "@/lib/workbenchGraph";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface ScenarioWorkbenchProps {
  report: ScenarioReport;
  initialDate?: string;
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

export function ScenarioWorkbench({ report, initialDate }: ScenarioWorkbenchProps) {
  const { t } = useI18n();
  const timeline = report.daily_timeline || [];
  const initialSnapshot = getInitialSnapshot(timeline, initialDate);
  const [selectedDate, setSelectedDate] = useState(initialSnapshot?.date || "");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const selectedSnapshot =
    timeline.find((snapshot) => snapshot.date === selectedDate) || initialSnapshot;

  const graph = useMemo(() => {
    return selectedSnapshot ? buildWorkbenchGraph(report, selectedSnapshot) : null;
  }, [report, selectedSnapshot]);

  const selectedNode =
    graph?.nodes.find((node) => node.id === selectedNodeId) || null;
  const selectedEdge =
    graph?.edges.find((edge) => edge.id === selectedEdgeId) || null;

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
          {t("workbench.openReport")}
        </Link>
        <section className="notice">
          <h1>{t("workbench.noTimelineTitle")}</h1>
          <p>
            {t("workbench.noTimeline")}
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="workbench-page">
      <header className="workbench-header">
        <div>
          <p className="muted">{t("workbench.productName")}</p>
          <h1>{report.title}</h1>
          <div className="tag-row">
            <span className="tag">{selectedSnapshot.date}</span>
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
            {t("workbench.openReport")}
          </Link>
          <Link className="button secondary" href="/scenarios">
            {t("common.scenarioList")}
          </Link>
        </div>
      </header>

      <DailyTimelineRail
        onSelectDate={selectDate}
        selectedDate={selectedSnapshot.date}
        timeline={timeline}
      />

      <main className="workbench-layout">
        <DailyGraphCanvas
          graph={graph}
          onSelectEdge={setSelectedEdgeId}
          onSelectNode={setSelectedNodeId}
          selectedEdgeId={selectedEdgeId}
          selectedNodeId={selectedNodeId}
        />
        <WorkbenchPanel
          graph={graph}
          selectedEdge={selectedEdge}
          selectedNode={selectedNode}
          snapshot={selectedSnapshot}
        />
      </main>
    </div>
  );
}

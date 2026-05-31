"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { DailyGraphCanvas } from "./DailyGraphCanvas";
import { DailyTimelineRail } from "./DailyTimelineRail";
import { WorkbenchPanel } from "./WorkbenchPanel";
import type { DailyScenarioSnapshot, ScenarioReport } from "@/lib/types";
import { buildWorkbenchGraph } from "@/lib/workbenchGraph";

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
  const timeline = report.daily_timeline || [];
  const initialSnapshot = getInitialSnapshot(timeline, initialDate);
  const [selectedDate, setSelectedDate] = useState(initialSnapshot?.date || "");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const selectedSnapshot =
    timeline.find((snapshot) => snapshot.date === selectedDate) || initialSnapshot;

  const graph = useMemo(() => {
    return selectedSnapshot ? buildWorkbenchGraph(report, selectedSnapshot) : null;
  }, [report, selectedSnapshot]);

  const selectedNode =
    graph?.nodes.find((node) => node.id === selectedNodeId) || null;

  const selectDate = (date: string) => {
    setSelectedDate(date);
    setSelectedNodeId(null);
  };

  if (!selectedSnapshot || !graph) {
    return (
      <div className="page stack">
        <Link
          className="button secondary"
          href={`/scenarios/${report.scenario_id}/report`}
        >
          Open report
        </Link>
        <section className="notice">
          <h1>Scenario Workbench</h1>
          <p>
            This saved report does not include a daily timeline, so the graph
            workbench cannot be built for it. Open the report view for the saved
            summary.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="workbench-page">
      <header className="workbench-header">
        <div>
          <p className="muted">Astro ABM Scenario Workbench</p>
          <h1>{report.title}</h1>
          <div className="tag-row">
            <span className="tag">{selectedSnapshot.date}</span>
            <span className="tag">
              {report.start_date} to {report.end_date}
            </span>
            <span className="tag">{report.mode}</span>
          </div>
        </div>
        <div className="button-row">
          <Link
            className="button secondary"
            href={`/scenarios/${report.scenario_id}/report`}
          >
            Open report
          </Link>
          <Link className="button secondary" href="/scenarios">
            Scenario list
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
          onSelectNode={setSelectedNodeId}
          selectedNodeId={selectedNodeId}
        />
        <WorkbenchPanel selectedNode={selectedNode} snapshot={selectedSnapshot} />
      </main>
    </div>
  );
}

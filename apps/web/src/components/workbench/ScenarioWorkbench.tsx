"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ContextCoverageSummaryCard } from "../ContextCoverageSummaryCard";
import { LlmScenarioReportCard } from "../LlmScenarioReportCard";
import { DailyGraphCanvas } from "./DailyGraphCanvas";
import { DailyTimelineRail } from "./DailyTimelineRail";
import { WorkbenchPanel } from "./WorkbenchPanel";
import type {
  DailyScenarioSnapshot,
  LlmProvider,
  ReportLanguage,
  ScenarioReport,
} from "@/lib/types";
import { generateScenarioWorldlineChunk } from "@/lib/api";
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
  const [currentReport, setCurrentReport] = useState(report);
  const [regeneration, setRegeneration] = useState<{
    active: boolean;
    message: string;
    error: string | null;
  }>({ active: false, message: "", error: null });
  const timeline = currentReport.daily_timeline || [];
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
    return selectedSnapshot ? buildWorkbenchGraph(currentReport, selectedSnapshot) : null;
  }, [currentReport, selectedSnapshot]);
  const assetStressSeries = useMemo(
    () => buildAssetStressSeries(currentReport, timeline),
    [currentReport, timeline],
  );

  const selectedNode =
    graph?.nodes.find((node) => node.id === selectedNodeId) || null;
  const selectedEdge =
    graph?.edges.find((edge) => edge.id === selectedEdgeId) || null;
  const selectedWorldlineDay =
    currentReport.worldline_simulation?.days.find(
      (day) => day.date === selectedSnapshot?.date,
    ) || null;

  const selectDate = (date: string) => {
    setSelectedDate(date);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  };

  const regenerateWorldline = async () => {
    if (!timeline.length || regeneration.active) {
      return;
    }
    const provenance = currentReport.worldline_simulation?.provenance || {};
    const storedWorldline =
      typeof currentReport.provenance.worldline === "object" &&
      currentReport.provenance.worldline !== null
        ? (currentReport.provenance.worldline as Record<string, unknown>)
        : {};
    const chunkSizeDays = normalizeChunkSize(provenance.chunk_size_days);
    const chunks = buildDateChunks(currentReport.start_date, currentReport.end_date, chunkSizeDays);
    const provider = normalizeLlmProvider(provenance.provider || storedWorldline.provider);
    const model = stringOrNull(provenance.model || storedWorldline.model);
    const baseUrl = stringOrNull(storedWorldline.base_url);
    let latestReport = currentReport;
    setRegeneration({
      active: true,
      message: `${t("worldline.regenerateRunning")} 0/${chunks.length}`,
      error: null,
    });
    try {
      for (const [index, chunk] of chunks.entries()) {
        setRegeneration({
          active: true,
          message: `${t("worldline.regenerateRunning")} ${index + 1}/${chunks.length}: ${chunk.start} → ${chunk.end}`,
          error: null,
        });
        const response = await generateScenarioWorldlineChunk(currentReport.scenario_id, {
          llm_provider: provider,
          llm_real_enabled: true,
          llm_base_url: baseUrl,
          llm_model: model,
          llm_api_key: null,
          llm_user_prompt: null,
          language: (currentReport.language || "en") as ReportLanguage,
          chunk_start_date: chunk.start,
          chunk_end_date: chunk.end,
          chunk_index: index + 1,
          total_chunks: chunks.length,
          worldline_chunk_days: chunkSizeDays,
        });
        latestReport = response.report;
        setCurrentReport(response.report);
      }
      setRegeneration({
        active: false,
        message: t("worldline.regenerateDone"),
        error: null,
      });
      if (!latestReport.daily_timeline?.some((snapshot) => snapshot.date === selectedDate)) {
        setSelectedDate(latestReport.daily_timeline?.[0]?.date || "");
      }
    } catch (error) {
      setRegeneration({
        active: false,
        message: "",
        error: error instanceof Error ? error.message : t("common.unknownError"),
      });
    }
  };

  if (!selectedSnapshot || !graph) {
    return (
      <div className="page stack">
        <Link
          className="button secondary"
          href={`/scenarios/${currentReport.scenario_id}/report`}
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
          <h1>{currentReport.title}</h1>
          <div className="tag-row">
            <span className="tag">{selectedSnapshot.date}</span>
            {isWorldline && currentReport.worldline_simulation ? (
              <>
                <span className="tag">
                  {t("worldline.status")}: {currentReport.worldline_simulation.status}
                </span>
                <span className="tag">
                  {t("worldline.dayCount")}: {selectedIndex + 1}/
                  {currentReport.worldline_simulation.horizon_days}
                </span>
              </>
            ) : null}
            <span className="tag">
              {currentReport.start_date} {t("common.to")} {currentReport.end_date}
            </span>
            <span className="tag">
              {formatEnumLabel(t, "scenario_mode", currentReport.mode)}
            </span>
            <span className="tag">
              {t("report.generatedLanguage")}:{" "}
              {formatEnumLabel(t, "report_language", currentReport.language || "legacy")}
            </span>
          </div>
        </div>
        <div className="button-row">
          <Link
            className="button secondary"
            href={`/scenarios/${currentReport.scenario_id}/report`}
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
        coverageSummary={currentReport.coverage_summary}
      />

      {!isWorldline ? <LlmScenarioReportCard compact llmReport={currentReport.llm_report} /> : null}

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
          worldlineSimulation={currentReport.worldline_simulation}
          onRegenerateWorldline={isWorldline ? regenerateWorldline : undefined}
          regenerationError={regeneration.error}
          regenerationMessage={regeneration.message}
          regenerationActive={regeneration.active}
          worldlinePrimary={isWorldline}
        />
      </main>
    </div>
  );
}

function normalizeChunkSize(value: unknown): 1 | 2 | 3 | 5 {
  return value === 1 || value === 2 || value === 3 || value === 5 ? value : 3;
}

function normalizeLlmProvider(value: unknown): LlmProvider {
  return value === "mock" || value === "openai_compatible"
    ? value
    : "openai_compatible";
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function buildDateChunks(startDate: string, endDate: string, chunkSizeDays: number) {
  const chunks: Array<{ start: string; end: string }> = [];
  let current = parseDate(startDate);
  const end = parseDate(endDate);
  while (current <= end) {
    const chunkStart = current;
    const chunkEnd = new Date(current);
    chunkEnd.setUTCDate(chunkEnd.getUTCDate() + chunkSizeDays - 1);
    if (chunkEnd > end) {
      chunkEnd.setTime(end.getTime());
    }
    chunks.push({ start: formatDate(chunkStart), end: formatDate(chunkEnd) });
    current = new Date(chunkEnd);
    current.setUTCDate(current.getUTCDate() + 1);
  }
  return chunks;
}

function parseDate(value: string) {
  return new Date(`${value}T00:00:00Z`);
}

function formatDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

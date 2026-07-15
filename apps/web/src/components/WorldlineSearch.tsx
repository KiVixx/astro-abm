"use client";

import { useMemo, useState } from "react";
import { WorldlineCard } from "./WorldlineCard";
import { deleteScenario } from "@/lib/api";
import type { ScenarioSummary } from "@/lib/types";
import { useI18n } from "@/i18n/useI18n";

type WorldlineFilter = "all" | "ready" | "llm" | "deterministic" | "failed" | "legacy";

export function WorldlineSearch({ summaries }: { summaries: ScenarioSummary[] }) {
  const { t } = useI18n();
  const [items, setItems] = useState(summaries);
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<WorldlineFilter>("all");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const normalizedQuery = query.trim().toLowerCase();
  const filterOptions = useMemo(
    () =>
      ([
        "all",
        "ready",
        "llm",
        "deterministic",
        "failed",
        "legacy",
      ] satisfies WorldlineFilter[]).map((filter) => ({
        filter,
        count: items.filter((report) => matchesWorldlineFilter(report, filter)).length,
      })),
    [items],
  );
  const filtered = useMemo(() => {
    return items.filter((report) => {
      if (!matchesWorldlineFilter(report, activeFilter)) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      const haystack = [
        report.title,
        report.description || "",
        report.worldline_status || "",
        report.worldline_generation_mode || "",
        report.llm_report_status || "",
        ...report.assets,
        ...report.agent_names,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [activeFilter, items, normalizedQuery]);

  const confirmAndDelete = async (report: ScenarioSummary) => {
    const confirmed = window.confirm(
      `${t("scenarios.deleteConfirm")}\n\n${report.title}`,
    );
    if (!confirmed) {
      return;
    }
    setDeletingId(report.scenario_id);
    try {
      await deleteScenario(report.scenario_id);
      setItems((current) =>
        current.filter((item) => item.scenario_id !== report.scenario_id),
      );
    } catch (error) {
      window.alert(
        `${t("scenarios.deleteFailed")}: ${
          error instanceof Error ? error.message : t("common.unknownError")
        }`,
      );
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="stack">
      <label className="form-field">
        <span>{t("worldline.searchLabel")}</span>
        <input
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("worldline.searchPlaceholder")}
          suppressHydrationWarning
          value={query}
        />
      </label>
      <div className="filter-row" role="list" aria-label={t("worldline.filterLabel")}>
        {filterOptions.map(({ count, filter }) => (
          <button
            aria-pressed={activeFilter === filter}
            className={`filter-chip ${activeFilter === filter ? "is-active" : ""}`}
            key={filter}
            onClick={() => setActiveFilter(filter)}
            type="button"
          >
            {t(`worldline.filter.${filter}`)} <span>{count}</span>
          </button>
        ))}
      </div>
      <div className="stack">
        {filtered.length ? (
          filtered.map((report) => (
            <WorldlineCard
              isDeleting={deletingId === report.scenario_id}
              key={report.scenario_id}
              onDelete={confirmAndDelete}
              report={report}
            />
          ))
        ) : (
          <div className="notice">{t("worldline.noMatches")}</div>
        )}
      </div>
    </section>
  );
}

function matchesWorldlineFilter(report: ScenarioSummary, filter: WorldlineFilter): boolean {
  if (filter === "all") {
    return true;
  }
  if (filter === "legacy") {
    return !report.worldline_status;
  }
  if (!report.worldline_status) {
    return false;
  }
  const generationMode = report.worldline_generation_mode || "";
  const failedChunks = Number(report.worldline_failed_chunk_count || 0);
  if (filter === "failed") {
    return (
      report.worldline_status === "failed" ||
      report.llm_report_status === "failed" ||
      report.llm_report_status === "invalid_output" ||
      failedChunks > 0
    );
  }
  if (filter === "llm") {
    return generationMode.includes("llm_chunk");
  }
  if (filter === "deterministic") {
    return generationMode.includes("deterministic");
  }
  if (filter === "ready") {
    return ["completed", "mock_completed"].includes(report.worldline_status);
  }
  return true;
}

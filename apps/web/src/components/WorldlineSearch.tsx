"use client";

import { useEffect, useMemo, useState } from "react";
import { WorldlineCard } from "./WorldlineCard";
import { deleteScenario } from "@/lib/api";
import type { ScenarioSummary } from "@/lib/types";
import { useI18n } from "@/i18n/useI18n";

type WorldlineFilter = "all" | "ready" | "llm" | "deterministic" | "failed" | "legacy";
type WorldlineSort = "newest" | "oldest" | "start_date";
const WORLDLINES_PAGE_SIZE = 12;

export function WorldlineSearch({
  initialFilter,
  initialQuery,
  initialSort,
  summaries,
}: {
  initialFilter?: string;
  initialQuery?: string;
  initialSort?: string;
  summaries: ScenarioSummary[];
}) {
  const { t } = useI18n();
  const [items, setItems] = useState(summaries);
  const [query, setQuery] = useState(initialQuery || "");
  const [activeFilter, setActiveFilter] = useState<WorldlineFilter>(() =>
    normalizeWorldlineFilter(initialFilter),
  );
  const [sortOrder, setSortOrder] = useState<WorldlineSort>(() =>
    normalizeWorldlineSort(initialSort),
  );
  const [visibleLimit, setVisibleLimit] = useState(WORLDLINES_PAGE_SIZE);
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
    const matchingItems = items.filter((report) => {
      if (!matchesWorldlineFilter(report, activeFilter)) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      const haystack = [
        report.scenario_id,
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
    return matchingItems.sort((left, right) => compareWorldlines(left, right, sortOrder));
  }, [activeFilter, items, normalizedQuery, sortOrder]);
  const visibleItems = filtered.slice(0, visibleLimit);
  const remainingCount = Math.max(0, filtered.length - visibleItems.length);

  useEffect(() => {
    setVisibleLimit(WORLDLINES_PAGE_SIZE);
  }, [activeFilter, normalizedQuery, sortOrder]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const url = new URL(window.location.href);
    if (query.trim()) {
      url.searchParams.set("q", query);
    } else {
      url.searchParams.delete("q");
    }
    if (activeFilter === "all") {
      url.searchParams.delete("status");
    } else {
      url.searchParams.set("status", activeFilter);
    }
    if (sortOrder === "newest") {
      url.searchParams.delete("sort");
    } else {
      url.searchParams.set("sort", sortOrder);
    }
    window.history.replaceState(window.history.state, "", url);
  }, [activeFilter, query, sortOrder]);

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
    <section className="worldline-archive">
      <div className="worldline-search-console">
        <div className="worldline-search-row">
          <label className="form-field worldline-search-field">
            <span>{t("worldline.searchLabel")}</span>
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("worldline.searchPlaceholder")}
              suppressHydrationWarning
              value={query}
            />
          </label>
          <div className="worldline-search-tools">
            <label className="worldline-sort-field">
              <span>{t("worldline.sortLabel")}</span>
              <select
                onChange={(event) => setSortOrder(event.target.value as WorldlineSort)}
                value={sortOrder}
              >
                <option value="newest">{t("worldline.sort.newest")}</option>
                <option value="oldest">{t("worldline.sort.oldest")}</option>
                <option value="start_date">{t("worldline.sort.startDate")}</option>
              </select>
            </label>
            <div className="worldline-result-count" aria-live="polite">
              <span>{t("worldline.recordsVisible")}</span>
              <strong>{String(filtered.length).padStart(2, "0")}</strong>
              <span>/ {String(items.length).padStart(2, "0")}</span>
            </div>
          </div>
        </div>
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
      </div>
      <div className="worldline-records">
        {filtered.length ? (
          <>
            {visibleItems.map((report) => (
              <WorldlineCard
                isDeleting={deletingId === report.scenario_id}
                key={report.scenario_id}
                onDelete={confirmAndDelete}
                report={report}
              />
            ))}
            {remainingCount > 0 ? (
              <div className="worldline-load-more">
                <button
                  className="button secondary"
                  onClick={() => setVisibleLimit((current) => current + WORLDLINES_PAGE_SIZE)}
                  type="button"
                >
                  {t("worldline.loadMore")} ({Math.min(WORLDLINES_PAGE_SIZE, remainingCount)})
                </button>
                <span aria-live="polite">
                  {t("worldline.recordsRemaining")}: {remainingCount}
                </span>
              </div>
            ) : null}
          </>
        ) : (
          <div className="worldline-empty-state">
            <span aria-hidden="true">00</span>
            <p>{t("worldline.noMatches")}</p>
            <button
              className="button secondary"
              onClick={() => {
                setQuery("");
                setActiveFilter("all");
              }}
              type="button"
            >
              {t("worldline.clearFilters")}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

function normalizeWorldlineFilter(value?: string): WorldlineFilter {
  return ["all", "ready", "llm", "deterministic", "failed", "legacy"].includes(
    value || "",
  )
    ? (value as WorldlineFilter)
    : "all";
}

function normalizeWorldlineSort(value?: string): WorldlineSort {
  return ["newest", "oldest", "start_date"].includes(value || "")
    ? (value as WorldlineSort)
    : "newest";
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
  const failedChunks = Number(
    report.worldline_llm_failed_chunk_count
      ?? report.worldline_failed_chunk_count
      ?? 0,
  );
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
    return (
      ["completed", "mock_completed"].includes(report.worldline_status)
      && failedChunks === 0
    );
  }
  return true;
}

function compareWorldlines(
  left: ScenarioSummary,
  right: ScenarioSummary,
  sortOrder: WorldlineSort,
): number {
  if (sortOrder === "oldest") {
    return left.created_at.localeCompare(right.created_at);
  }
  if (sortOrder === "start_date") {
    return right.start_date.localeCompare(left.start_date)
      || right.created_at.localeCompare(left.created_at);
  }
  return right.created_at.localeCompare(left.created_at);
}

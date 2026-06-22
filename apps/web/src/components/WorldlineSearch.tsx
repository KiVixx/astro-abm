"use client";

import { useMemo, useState } from "react";
import { WorldlineCard } from "./WorldlineCard";
import { deleteScenario } from "@/lib/api";
import type { ScenarioReport } from "@/lib/types";
import { useI18n } from "@/i18n/useI18n";

export function WorldlineSearch({ reports }: { reports: ScenarioReport[] }) {
  const { t } = useI18n();
  const [items, setItems] = useState(reports);
  const [query, setQuery] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const normalizedQuery = query.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!normalizedQuery) {
      return items;
    }
    return items.filter((report) => {
      const haystack = [
        report.title,
        report.description || "",
        report.worldline_simulation?.status || "",
        report.worldline_simulation?.mode || "",
        report.llm_report?.status || "",
        ...report.assets,
        ...report.agents.map((agent) => agent.name),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [items, normalizedQuery]);

  const confirmAndDelete = async (report: ScenarioReport) => {
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

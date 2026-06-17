"use client";

import { useMemo, useState } from "react";
import { ScenarioCard } from "./ScenarioCard";
import { deleteScenario } from "@/lib/api";
import type { ScenarioSummary } from "@/lib/types";
import { useI18n } from "@/i18n/useI18n";

export function ScenarioSearch({ scenarios }: { scenarios: ScenarioSummary[] }) {
  const { t } = useI18n();
  const [scenarioItems, setScenarioItems] = useState(scenarios);
  const [deletingScenarioId, setDeletingScenarioId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const filteredScenarios = useMemo(() => {
    if (!normalizedQuery) {
      return scenarioItems;
    }
    return scenarioItems.filter((scenario) => {
      const haystack = [
        scenario.title,
        scenario.description || "",
        scenario.visibility,
        ...scenario.assets,
        ...scenario.agent_names,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [normalizedQuery, scenarioItems]);

  const confirmAndDelete = async (scenario: ScenarioSummary) => {
    const confirmed = window.confirm(
      `${t("scenarios.deleteConfirm")}\n\n${scenario.title}`,
    );
    if (!confirmed) {
      return;
    }
    setDeletingScenarioId(scenario.scenario_id);
    try {
      await deleteScenario(scenario.scenario_id);
      setScenarioItems((items) =>
        items.filter((item) => item.scenario_id !== scenario.scenario_id),
      );
    } catch (error) {
      window.alert(
        `${t("scenarios.deleteFailed")}: ${
          error instanceof Error ? error.message : t("common.unknownError")
        }`,
      );
    } finally {
      setDeletingScenarioId(null);
    }
  };

  return (
    <section className="stack">
      <label className="form-field">
        <span>{t("scenarios.searchLabel")}</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("scenarios.searchPlaceholder")}
        />
      </label>
      <div className="stack">
        {filteredScenarios.length ? (
          filteredScenarios.map((scenario) => (
            <ScenarioCard
              isDeleting={deletingScenarioId === scenario.scenario_id}
              key={scenario.scenario_id}
              onDelete={confirmAndDelete}
              scenario={scenario}
            />
          ))
        ) : (
          <div className="notice">{t("scenarios.noMatches")}</div>
        )}
      </div>
    </section>
  );
}

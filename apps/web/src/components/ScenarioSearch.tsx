"use client";

import { useMemo, useState } from "react";
import { ScenarioCard } from "./ScenarioCard";
import type { ScenarioSummary } from "@/lib/types";

export function ScenarioSearch({ scenarios }: { scenarios: ScenarioSummary[] }) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const filteredScenarios = useMemo(() => {
    if (!normalizedQuery) {
      return scenarios;
    }
    return scenarios.filter((scenario) => {
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
  }, [normalizedQuery, scenarios]);

  return (
    <section className="stack">
      <label className="form-field">
        <span>Search by title, asset, agent, or visibility</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="BTC, Macro Allocator, private..."
        />
      </label>
      <div className="stack">
        {filteredScenarios.length ? (
          filteredScenarios.map((scenario) => (
            <ScenarioCard key={scenario.scenario_id} scenario={scenario} />
          ))
        ) : (
          <div className="notice">No scenarios match the current search.</div>
        )}
      </div>
    </section>
  );
}

"use client";

import Link from "next/link";
import type { ScenarioSummary } from "@/lib/types";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

export function ScenarioCard({ scenario }: { scenario: ScenarioSummary }) {
  const { t } = useI18n();

  return (
    <article className="card">
      <h3>
        <Link href={`/scenarios/${scenario.scenario_id}`}>{scenario.title}</Link>
      </h3>
      {scenario.description ? <p className="muted">{scenario.description}</p> : null}
      <p className="muted">
        {scenario.start_date} {t("common.to")} {scenario.end_date}
      </p>
      <div className="tag-row">
        {scenario.assets.map((asset) => (
          <span className="tag" key={asset}>
            {asset}
          </span>
        ))}
        {scenario.agent_names.map((agentName, index) => (
          <span className="tag" key={`${agentName}-${index}`}>
            {formatAgentName(t, scenario.agent_ids[index] || "", agentName)}
          </span>
        ))}
        <span className="tag">
          {formatEnumLabel(t, "visibility", scenario.visibility)}
        </span>
      </div>
    </article>
  );
}

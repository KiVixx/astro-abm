import Link from "next/link";
import type { ScenarioSummary } from "@/lib/types";

export function ScenarioCard({ scenario }: { scenario: ScenarioSummary }) {
  return (
    <article className="card">
      <h3>
        <Link href={`/scenarios/${scenario.scenario_id}`}>{scenario.title}</Link>
      </h3>
      {scenario.description ? <p className="muted">{scenario.description}</p> : null}
      <p className="muted">
        {scenario.start_date} to {scenario.end_date}
      </p>
      <div className="tag-row">
        {scenario.assets.map((asset) => (
          <span className="tag" key={asset}>
            {asset}
          </span>
        ))}
        {scenario.agent_names.map((agentName) => (
          <span className="tag" key={agentName}>
            {agentName}
          </span>
        ))}
        <span className="tag">{scenario.visibility}</span>
      </div>
    </article>
  );
}

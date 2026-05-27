import type { ScenarioReport } from "@/lib/types";

function JsonBlock({ value }: { value: unknown }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}

export function ReportViewer({ report }: { report: ScenarioReport }) {
  return (
    <article className="stack">
      <section className="card">
        <h1>{report.title}</h1>
        {report.description ? <p className="lead">{report.description}</p> : null}
        <div className="tag-row">
          <span className="tag">
            {report.start_date} to {report.end_date}
          </span>
          {report.assets.map((asset) => (
            <span className="tag" key={asset}>
              {asset}
            </span>
          ))}
          <span className="tag">{report.visibility}</span>
        </div>
      </section>

      <section className="card">
        <h2>Simulation summary</h2>
        <p>{report.simulation_summary}</p>
      </section>

      <section className="card">
        <h2>Agents</h2>
        <div className="grid">
          {report.agents.map((agent) => (
            <div key={agent.agent_id}>
              <h3>{agent.name}</h3>
              <p className="muted">{agent.description}</p>
              <div className="tag-row">
                <span className="tag">{agent.category}</span>
                <span className="tag">{agent.risk_tolerance}</span>
                <span className="tag">{agent.time_horizon}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Daily context</h2>
        <JsonBlock value={report.daily_context} />
      </section>

      <section className="card">
        <h2>Agent outputs</h2>
        <div className="stack">
          {report.agent_outputs.map((output) => (
            <div key={output.agent_id}>
              <h3>{output.agent_name}</h3>
              <p>{output.behavior_summary}</p>
              <p>{output.likely_reaction}</p>
              <div className="tag-row">
                <span className="tag">{output.role}</span>
                <span className="tag">{output.risk_appetite}</span>
                <span className="tag">{output.confidence}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid">
        <div className="card">
          <h2>Risks</h2>
          <ul>
            {report.risks.map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h2>Caveats</h2>
          <ul>
            {report.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="card">
        <h2>Provenance</h2>
        <JsonBlock value={report.provenance} />
      </section>

      <section className="notice">
        <h2>Disclaimer</h2>
        <p>{report.disclaimer}</p>
      </section>

      <section className="card">
        <h2>Markdown report</h2>
        <pre>{report.markdown_report}</pre>
      </section>
    </article>
  );
}

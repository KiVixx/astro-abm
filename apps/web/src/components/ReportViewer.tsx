import type { ScenarioReport } from "@/lib/types";

function JsonBlock({ value }: { value: unknown }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}

export function ReportViewer({ report }: { report: ScenarioReport }) {
  const scenarioSummary = report.scenario_summary || report.simulation_summary;
  const riskThemes = report.risk_themes?.length ? report.risk_themes : report.risks;
  const dailyTimeline = report.daily_timeline || [];

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
        <h2>Summary</h2>
        <p>{scenarioSummary}</p>
      </section>

      <section className="card">
        <h2>Daily Timeline</h2>
        {dailyTimeline.length ? (
          <div className="timeline-list">
            {dailyTimeline.map((snapshot) => (
              <details className="timeline-detail" key={snapshot.date}>
                <summary className="timeline-summary">
                  <span>
                    <strong>{snapshot.date}</strong>
                    <br />
                    <span className="muted">Day {snapshot.day_index}</span>
                  </span>
                  <span>{snapshot.astro_context.intensity}</span>
                  <span>{snapshot.market_context.stress_regime}</span>
                  <span>{snapshot.market_context.volatility_regime}</span>
                  <span>{snapshot.market_context.liquidity_regime}</span>
                  <span>{snapshot.daily_risk_themes.slice(0, 2).join(", ")}</span>
                  <span>{snapshot.confidence}</span>
                </summary>
                <div className="timeline-detail-body">
                  <p>{snapshot.daily_summary}</p>
                  <div className="grid">
                    <div>
                      <h3>Astro context</h3>
                      <p>{snapshot.astro_context.summary}</p>
                      <div className="tag-row">
                        {snapshot.astro_context.event_tags.map((tag) => (
                          <span className="tag" key={tag}>
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h3>Market context</h3>
                      <p>{snapshot.market_context.summary}</p>
                      <div className="tag-row">
                        <span className="tag">
                          stress: {snapshot.market_context.stress_regime}
                        </span>
                        <span className="tag">
                          volatility: {snapshot.market_context.volatility_regime}
                        </span>
                        <span className="tag">
                          liquidity: {snapshot.market_context.liquidity_regime}
                        </span>
                      </div>
                    </div>
                  </div>
                  <h3>Agent states</h3>
                  <div className="stack">
                    {snapshot.agent_states.map((state) => (
                      <div className="nested-panel" key={state.agent_id}>
                        <strong>{state.agent_name}</strong>
                        <p>{state.likely_reaction}</p>
                        <div className="tag-row">
                          <span className="tag">{state.mood}</span>
                          <span className="tag">{state.risk_appetite}</span>
                          {state.attention_triggers.map((trigger) => (
                            <span className="tag" key={trigger}>
                              {trigger}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="grid section">
                    <div>
                      <h3>Daily risk themes</h3>
                      <ul>
                        {snapshot.daily_risk_themes.map((theme) => (
                          <li key={theme}>{theme}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h3>Caveats</h3>
                      <ul>
                        {snapshot.caveats.map((caveat) => (
                          <li key={caveat}>{caveat}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <p className="notice">{snapshot.disclaimer}</p>
                </div>
              </details>
            ))}
          </div>
        ) : (
          <div className="notice">
            This saved report does not include a daily timeline yet. Open a newly
            generated scenario to inspect individual days.
          </div>
        )}
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
          <h2>Risk Themes</h2>
          <ul>
            {riskThemes.map((risk) => (
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

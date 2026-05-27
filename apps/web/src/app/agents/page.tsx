import { getAgents } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  try {
    const agents = await getAgents();
    return (
      <div className="page stack">
        <header>
          <h1>Agents</h1>
          <p className="lead">
            Default archetypes used by local scenario rehearsals.
          </p>
        </header>
        <section className="grid">
          {agents.map((agent) => (
            <article className="card" key={agent.agent_id}>
              <h2>{agent.name}</h2>
              <p className="muted">{agent.description}</p>
              <div className="tag-row">
                <span className="tag">{agent.category}</span>
                <span className="tag">{agent.risk_tolerance}</span>
                <span className="tag">{agent.time_horizon}</span>
              </div>
              <dl>
                <dt>Macro sensitivity</dt>
                <dd>{agent.macro_sensitivity}</dd>
                <dt>Astro narrative sensitivity</dt>
                <dd>{agent.astro_narrative_sensitivity}</dd>
                <dt>Liquidity sensitivity</dt>
                <dd>{agent.liquidity_sensitivity}</dd>
                <dt>Decision style</dt>
                <dd>{agent.decision_style}</dd>
              </dl>
            </article>
          ))}
        </section>
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack">
        <h1>Agents</h1>
        <div className="notice">
          The API is not reachable. Start it with <code>make api</code> and reload
          this page.
        </div>
        <p className="muted">{error instanceof Error ? error.message : "Unknown error"}</p>
      </div>
    );
  }
}

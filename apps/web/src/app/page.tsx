import Link from "next/link";

export default function HomePage() {
  return (
    <div className="page">
      <section className="hero home-hero">
        <div>
          <h1>Astro ABM Scenario Platform</h1>
          <p className="lead">
            A local-first workspace for creating and reviewing AI market scenario
            rehearsals from Astro ABM daily research context.
          </p>
          <div className="actions">
            <Link className="button" href="/scenarios">
              Search scenarios
            </Link>
            <Link className="button secondary" href="/scenarios/new">
              Create scenario
            </Link>
          </div>
        </div>
      </section>

      <section className="disclaimer-grid">
        <div className="card">
          <h2>Daily data first</h2>
          <p className="muted">
            The MVP is shaped around daily association context and mock scenario
            outputs. It does not run point-in-time trading research in the UI.
          </p>
        </div>
        <div className="card">
          <h2>Agent groups</h2>
          <p className="muted">
            Retail, leveraged, macro, bank, company-type, and holder archetypes
            review the same scenario through different risk lenses.
          </p>
        </div>
        <div className="card">
          <h2>Local reports</h2>
          <p className="muted">
            Generated JSON and Markdown reports stay local and are ignored by git.
          </p>
        </div>
      </section>
    </div>
  );
}

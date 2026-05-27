import Link from "next/link";
import { ScenarioSearch } from "@/components/ScenarioSearch";
import { getScenarios } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ScenariosPage() {
  try {
    const scenarios = await getScenarios();
    return (
      <div className="page stack">
        <header>
          <h1>Scenarios</h1>
          <p className="lead">
            Search saved local scenario summaries without loading full Markdown
            reports until a scenario is opened.
          </p>
          <div className="actions">
            <Link className="button" href="/scenarios/new">
              Create scenario
            </Link>
          </div>
        </header>
        <ScenarioSearch scenarios={scenarios} />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack">
        <h1>Scenarios</h1>
        <div className="notice">
          The API is not reachable. Start it with <code>make api</code> and reload
          this page.
        </div>
        <p className="muted">{error instanceof Error ? error.message : "Unknown error"}</p>
      </div>
    );
  }
}

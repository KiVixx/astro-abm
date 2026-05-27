import Link from "next/link";
import { ScenarioForm } from "@/components/ScenarioForm";
import { getAgents } from "@/lib/api";
import { createScenarioAction } from "./actions";

export const dynamic = "force-dynamic";

export default async function NewScenarioPage() {
  try {
    const agents = await getAgents();
    return (
      <div className="page stack">
        <header>
          <h1>Create scenario</h1>
          <p className="lead">
            Generate a local mock scenario report through the FastAPI product API.
          </p>
        </header>
        <ScenarioForm agents={agents} action={createScenarioAction} />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack">
        <h1>Create scenario</h1>
        <div className="notice">
          The API is not reachable. Start it with <code>make api</code> before
          creating a scenario.
        </div>
        <p className="muted">{error instanceof Error ? error.message : "Unknown error"}</p>
        <Link className="button secondary" href="/">
          Back home
        </Link>
      </div>
    );
  }
}

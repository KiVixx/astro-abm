import { notFound } from "next/navigation";
import { ScenarioWorkbench } from "@/components/workbench/ScenarioWorkbench";
import { ApiError, getScenario } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ScenarioWorkbenchPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ date?: string }>;
}) {
  const { id } = await params;
  const { date } = await searchParams;

  try {
    const report = await getScenario(id);
    return <ScenarioWorkbench initialDate={date} report={report} />;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    return (
      <div className="page stack">
        <h1>Scenario workbench</h1>
        <div className="notice">
          The scenario could not be loaded. Check that the API is running.
        </div>
        <p className="muted">{error instanceof Error ? error.message : "Unknown error"}</p>
      </div>
    );
  }
}


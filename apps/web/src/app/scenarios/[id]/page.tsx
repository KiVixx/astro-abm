import Link from "next/link";
import { notFound } from "next/navigation";
import { ReportViewer } from "@/components/ReportViewer";
import { ApiError, getScenario } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ScenarioDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  try {
    const { id } = await params;
    const report = await getScenario(id);
    return (
      <div className="page stack">
        <Link className="button secondary" href="/scenarios">
          Back to scenarios
        </Link>
        <ReportViewer report={report} />
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    return (
      <div className="page stack">
        <h1>Scenario detail</h1>
        <div className="notice">
          The scenario could not be loaded. Check that the API is running.
        </div>
        <p className="muted">{error instanceof Error ? error.message : "Unknown error"}</p>
      </div>
    );
  }
}

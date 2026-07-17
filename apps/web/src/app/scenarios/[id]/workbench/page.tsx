import { notFound } from "next/navigation";
import { ScenarioWorkbench } from "@/components/workbench/ScenarioWorkbench";
import { I18nText } from "@/i18n/useI18n";
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
    const report = await getScenario(id, { includeMarkdown: false });
    return <ScenarioWorkbench initialDate={date} report={report} />;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    return (
      <div className="page stack">
        <h1>
          <I18nText tKey="workbench.noTimelineTitle" />
        </h1>
        <div className="notice">
          <I18nText tKey="workbench.loadError" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
      </div>
    );
  }
}

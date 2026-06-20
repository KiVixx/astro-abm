import Link from "next/link";
import { notFound } from "next/navigation";
import { ReportViewer } from "@/components/ReportViewer";
import { I18nText } from "@/i18n/useI18n";
import { ApiError, getScenario } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ScenarioReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  try {
    const { id } = await params;
    const report = await getScenario(id);
    return (
      <div className="page stack">
        <div className="button-row">
          <Link className="button" href={`/worldlines/${report.scenario_id}`}>
            <I18nText tKey="worldline.openWorldline" />
          </Link>
          <Link className="button secondary" href={`/scenarios/${report.scenario_id}`}>
            <I18nText tKey="common.backToWorkbench" />
          </Link>
          <Link className="button secondary" href="/worldlines">
            <I18nText tKey="worldline.backToWorldlines" />
          </Link>
          <Link className="button secondary" href="/scenarios">
            <I18nText tKey="common.backToScenarios" />
          </Link>
        </div>
        <ReportViewer report={report} />
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    return (
      <div className="page stack">
        <h1>
          <I18nText tKey="report.markdownReport" />
        </h1>
        <div className="notice">
          <I18nText tKey="report.loadError" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
      </div>
    );
  }
}

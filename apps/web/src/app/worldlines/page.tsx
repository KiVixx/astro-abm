import Link from "next/link";
import { WorldlineSearch } from "@/components/WorldlineSearch";
import { I18nText } from "@/i18n/useI18n";
import { getScenario, getScenarios } from "@/lib/api";
import type { ScenarioReport } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function WorldlinesPage() {
  try {
    const summaries = await getScenarios();
    const reports = (
      await Promise.all(
        summaries.map(async (summary) => {
          try {
            return await getScenario(summary.scenario_id);
          } catch {
            return null;
          }
        }),
      )
    ).filter((report): report is ScenarioReport => report !== null);

    return (
      <div className="page stack">
        <header>
          <h1>
            <I18nText tKey="worldline.listTitle" />
          </h1>
          <p className="lead">
            <I18nText tKey="worldline.listLead" />
          </p>
          <div className="actions">
            <Link className="button" href="/worldlines/new">
              <I18nText tKey="worldline.create" />
            </Link>
            <Link className="button secondary" href="/scenarios">
              <I18nText tKey="worldline.openScenarioLibrary" />
            </Link>
          </div>
        </header>
        <WorldlineSearch reports={reports} />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack">
        <h1>
          <I18nText tKey="worldline.listTitle" />
        </h1>
        <div className="notice">
          <I18nText tKey="scenarios.apiUnavailable" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
      </div>
    );
  }
}

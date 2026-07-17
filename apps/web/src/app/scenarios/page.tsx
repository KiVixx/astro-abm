import Link from "next/link";
import { ScenarioSearch } from "@/components/ScenarioSearch";
import { I18nText } from "@/i18n/useI18n";
import { getScenarios } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ScenariosPage() {
  try {
    const scenarios = await getScenarios();
    return (
      <div className="page stack">
        <header>
          <h1>
            <I18nText tKey="scenarios.title" />
          </h1>
          <p className="lead">
            <I18nText tKey="scenarios.lead" />
          </p>
          <div className="actions">
            <Link className="button" href="/scenarios/new">
              <I18nText tKey="scenarios.create" />
            </Link>
          </div>
        </header>
        <ScenarioSearch scenarios={scenarios} />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack">
        <h1>
          <I18nText tKey="scenarios.title" />
        </h1>
        <div className="notice">
          <I18nText tKey="scenarios.apiUnavailable" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
        <Link className="button secondary" href="/scenarios">
          <I18nText tKey="common.retry" />
        </Link>
      </div>
    );
  }
}

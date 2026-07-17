import Link from "next/link";
import { WorldlineSearch } from "@/components/WorldlineSearch";
import { I18nText } from "@/i18n/useI18n";
import { getScenarios } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function WorldlinesPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; sort?: string; status?: string }>;
}) {
  try {
    const { q, sort, status } = await searchParams;
    const summaries = await getScenarios();

    return (
      <div className="page stack worldline-index-page">
        <header className="worldline-index-header">
          <div className="worldline-index-copy">
            <p className="pixel-kicker">
              <I18nText tKey="worldline.archiveKicker" /> // {String(summaries.length).padStart(2, "0")}
            </p>
            <h1>
              <I18nText tKey="worldline.listTitle" />
            </h1>
            <p className="lead">
              <I18nText tKey="worldline.listLead" />
            </p>
          </div>
          <div className="worldline-index-actions">
            <Link className="button" href="/worldlines/new">
              <I18nText tKey="worldline.create" />
            </Link>
            <Link className="button secondary" href="/scenarios">
              <I18nText tKey="worldline.openScenarioLibrary" />
            </Link>
          </div>
        </header>
        <WorldlineSearch
          initialFilter={status}
          initialQuery={q}
          initialSort={sort}
          summaries={summaries}
        />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack worldline-index-page">
        <h1>
          <I18nText tKey="worldline.listTitle" />
        </h1>
        <div className="notice">
          <I18nText tKey="scenarios.apiUnavailable" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
        <Link className="button secondary" href="/worldlines">
          <I18nText tKey="common.retry" />
        </Link>
      </div>
    );
  }
}

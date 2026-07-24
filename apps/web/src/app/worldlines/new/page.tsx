import Link from "next/link";
import { ScenarioForm } from "@/components/ScenarioForm";
import { I18nText } from "@/i18n/useI18n";
import { getAgents, getAssets, getLlmPresets } from "@/lib/api";
import { serverCookieHeader } from "@/lib/serverAuth";

export const dynamic = "force-dynamic";

export default async function NewWorldlinePage() {
  try {
    const cookieHeader = await serverCookieHeader();
    const [agents, marketSeries, llmPresets] = await Promise.all([
      getAgents(),
      getAssets(cookieHeader),
      getLlmPresets(),
    ]);
    return (
      <div className="page stack worldline-create-page">
        <header className="worldline-create-header">
          <p className="pixel-kicker">
            <I18nText tKey="worldline.createKicker" />
          </p>
          <h1>
            <I18nText tKey="worldline.create" />
          </h1>
          <p className="lead">
            <I18nText tKey="worldline.createLead" />
          </p>
        </header>
        <ScenarioForm
          agents={agents}
          marketSeries={marketSeries}
          initialLlmPresets={llmPresets}
          product="worldline"
        />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack worldline-create-page">
        <h1>
          <I18nText tKey="worldline.create" />
        </h1>
        <div className="notice">
          <I18nText tKey="scenarioCreate.apiUnavailable" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
        <div className="button-row">
          <Link className="button" href="/worldlines/new">
            <I18nText tKey="common.retry" />
          </Link>
          <Link className="button secondary" href="/">
            <I18nText tKey="common.backHome" />
          </Link>
        </div>
      </div>
    );
  }
}

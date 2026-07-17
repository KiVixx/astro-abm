import Link from "next/link";
import { ScenarioForm } from "@/components/ScenarioForm";
import { I18nText } from "@/i18n/useI18n";
import { getAgents, getAssets, getLlmPresets } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function NewScenarioPage() {
  try {
    const [agents, marketSeries, llmPresets] = await Promise.all([
      getAgents(),
      getAssets(),
      getLlmPresets(),
    ]);
    return (
      <div className="page stack">
        <header>
          <h1>
            <I18nText tKey="scenarioCreate.title" />
          </h1>
          <p className="lead">
            <I18nText tKey="scenarioCreate.lead" />
          </p>
        </header>
        <ScenarioForm
          agents={agents}
          marketSeries={marketSeries}
          initialLlmPresets={llmPresets}
        />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack">
        <h1>
          <I18nText tKey="scenarioCreate.title" />
        </h1>
        <div className="notice">
          <I18nText tKey="scenarioCreate.apiUnavailable" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
        <Link className="button secondary" href="/">
          <I18nText tKey="common.backHome" />
        </Link>
      </div>
    );
  }
}

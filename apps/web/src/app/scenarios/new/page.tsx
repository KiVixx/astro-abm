import Link from "next/link";
import { ScenarioForm } from "@/components/ScenarioForm";
import { I18nText } from "@/i18n/useI18n";
import { getAgents, getAssets } from "@/lib/api";
import {
  createScenarioForProgressAction,
  generateScenarioLlmChunkAction,
} from "./actions";

export const dynamic = "force-dynamic";

export default async function NewScenarioPage() {
  try {
    const [agents, marketSeries] = await Promise.all([getAgents(), getAssets()]);
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
          chunkAction={generateScenarioLlmChunkAction}
          createAction={createScenarioForProgressAction}
          agents={agents}
          marketSeries={marketSeries}
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

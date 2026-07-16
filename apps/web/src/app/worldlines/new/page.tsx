import Link from "next/link";
import { ScenarioForm } from "@/components/ScenarioForm";
import { I18nText } from "@/i18n/useI18n";
import { getAgents, getAssets, getLlmPresets } from "@/lib/api";
import {
  createScenarioForProgressAction,
  generateScenarioLlmChunkAction,
  generateScenarioWorldlineChunkAction,
} from "../../scenarios/new/actions";

export const dynamic = "force-dynamic";

export default async function NewWorldlinePage() {
  try {
    const [agents, marketSeries, llmPresets] = await Promise.all([
      getAgents(),
      getAssets(),
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
          chunkAction={generateScenarioLlmChunkAction}
          createAction={createScenarioForProgressAction}
          marketSeries={marketSeries}
          initialLlmPresets={llmPresets}
          product="worldline"
          worldlineChunkAction={generateScenarioWorldlineChunkAction}
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
        <Link className="button secondary" href="/">
          <I18nText tKey="common.backHome" />
        </Link>
      </div>
    );
  }
}

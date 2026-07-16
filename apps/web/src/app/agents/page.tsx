import { AgentGrid } from "@/components/AgentGrid";
import { I18nText } from "@/i18n/useI18n";
import { getAgents } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  try {
    const agents = await getAgents();
    return (
      <div className="page stack agents-page">
        <header className="agents-header">
          <p className="pixel-kicker">
            <I18nText tKey="agents.directoryKicker" />
          </p>
          <h1>
            <I18nText tKey="agents.title" />
          </h1>
          <p className="lead">
            <I18nText tKey="agents.lead" />
          </p>
          <p className="agents-directory-count">
            <strong>{agents.length}</strong> <I18nText tKey="agents.profilesLoaded" />
          </p>
        </header>
        <AgentGrid agents={agents} />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack agents-page">
        <h1>
          <I18nText tKey="agents.title" />
        </h1>
        <div className="notice">
          <I18nText tKey="agents.apiUnavailable" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
      </div>
    );
  }
}

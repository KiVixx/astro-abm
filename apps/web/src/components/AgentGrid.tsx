"use client";

import type { AgentProfile } from "@/lib/types";
import {
  formatAgentDescription,
  formatAgentProfileName,
  formatEnumLabel,
} from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

export function AgentGrid({ agents }: { agents: AgentProfile[] }) {
  const { t } = useI18n();

  return (
    <section className="agent-directory">
      {agents.map((agent, index) => (
        <article
          className={`agent-profile-record agent-category-${agent.category}`}
          key={agent.agent_id}
        >
          <header className="agent-record-header">
            <span className="agent-record-id">AG-{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h2>{formatAgentProfileName(t, agent)}</h2>
              <p>{formatEnumLabel(t, "agent_category", agent.category)}</p>
            </div>
          </header>
          <p className="agent-record-description">
            {formatAgentDescription(t, agent.agent_id, agent.description)}
          </p>
          <div className="agent-core-facts">
            <div>
              <span>{t("agents.riskTolerance")}</span>
              <strong>{formatEnumLabel(t, "agent_level", agent.risk_tolerance)}</strong>
            </div>
            <div>
              <span>{t("agents.timeHorizon")}</span>
              <strong>{formatEnumLabel(t, "time_horizon", agent.time_horizon)}</strong>
            </div>
          </div>
          <dl className="agent-sensitivity-grid">
            <div>
              <dt>{t("agents.macroSensitivity")}</dt>
              <dd>{formatEnumLabel(t, "agent_level", agent.macro_sensitivity)}</dd>
            </div>
            <div>
              <dt>{t("agents.astroNarrativeSensitivity")}</dt>
              <dd>{formatEnumLabel(t, "agent_level", agent.astro_narrative_sensitivity)}</dd>
            </div>
            <div>
              <dt>{t("agents.liquiditySensitivity")}</dt>
              <dd>{formatEnumLabel(t, "agent_level", agent.liquidity_sensitivity)}</dd>
            </div>
            <div className="agent-decision-style">
              <dt>{t("agents.decisionStyle")}</dt>
              <dd>{formatEnumLabel(t, "decision_style", agent.decision_style)}</dd>
            </div>
          </dl>
        </article>
      ))}
    </section>
  );
}

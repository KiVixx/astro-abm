"use client";

import type { AgentProfile } from "@/lib/types";
import { formatAgentProfileName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

export function AgentGrid({ agents }: { agents: AgentProfile[] }) {
  const { t } = useI18n();

  return (
    <section className="grid">
      {agents.map((agent) => (
        <article className="card" key={agent.agent_id}>
          <h2>{formatAgentProfileName(t, agent)}</h2>
          <p className="muted">{agent.description}</p>
          <div className="tag-row">
            <span className="tag">
              {formatEnumLabel(t, "agent_category", agent.category)}
            </span>
            <span className="tag">{agent.risk_tolerance}</span>
            <span className="tag">{agent.time_horizon}</span>
          </div>
          <dl>
            <dt>{t("agents.macroSensitivity")}</dt>
            <dd>{agent.macro_sensitivity}</dd>
            <dt>{t("agents.astroNarrativeSensitivity")}</dt>
            <dd>{agent.astro_narrative_sensitivity}</dd>
            <dt>{t("agents.liquiditySensitivity")}</dt>
            <dd>{agent.liquidity_sensitivity}</dd>
            <dt>{t("agents.decisionStyle")}</dt>
            <dd>{agent.decision_style}</dd>
          </dl>
        </article>
      ))}
    </section>
  );
}


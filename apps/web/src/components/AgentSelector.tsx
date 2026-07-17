"use client";

import type { AgentProfile } from "@/lib/types";
import { formatAgentProfileName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

export function AgentSelector({ agents }: { agents: AgentProfile[] }) {
  const { t } = useI18n();
  const defaultAgentIds = new Set([
    "crypto_retail_fomo",
    "leveraged_trader",
    "macro_allocator",
  ]);

  return (
    <div className="checkbox-grid">
      {agents.map((agent) => (
        <label className="checkbox-card" key={agent.agent_id}>
          <input
            defaultChecked={defaultAgentIds.has(agent.agent_id)}
            name="agent_ids"
            type="checkbox"
            value={agent.agent_id}
          />
          <span>
            <strong>{formatAgentProfileName(t, agent)}</strong>
            <br />
            <span className="muted">
              {formatEnumLabel(t, "agent_category", agent.category)} ·{" "}
              {formatEnumLabel(t, "time_horizon", agent.time_horizon)} ·{" "}
              {formatEnumLabel(t, "decision_style", agent.decision_style)}
            </span>
          </span>
        </label>
      ))}
    </div>
  );
}

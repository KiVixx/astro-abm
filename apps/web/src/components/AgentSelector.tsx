import type { AgentProfile } from "@/lib/types";

export function AgentSelector({ agents }: { agents: AgentProfile[] }) {
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
            <strong>{agent.name}</strong>
            <br />
            <span className="muted">
              {agent.category} · {agent.time_horizon} · {agent.decision_style}
            </span>
          </span>
        </label>
      ))}
    </div>
  );
}

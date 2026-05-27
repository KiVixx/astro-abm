import { AgentSelector } from "./AgentSelector";
import type { AgentProfile } from "@/lib/types";

export function ScenarioForm({
  agents,
  action,
}: {
  agents: AgentProfile[];
  action: (formData: FormData) => Promise<void>;
}) {
  return (
    <form action={action} className="stack">
      <div className="form-grid">
        <label className="form-field full">
          <span>Title</span>
          <input
            name="title"
            required
            defaultValue="2026 Q3 BTC ETH Daily Scenario"
          />
        </label>
        <label className="form-field full">
          <span>Description</span>
          <textarea
            name="description"
            defaultValue="Local mock scenario rehearsal using daily association context."
          />
        </label>
        <label className="form-field">
          <span>Start date</span>
          <input name="start_date" required type="date" defaultValue="2026-07-01" />
        </label>
        <label className="form-field">
          <span>End date</span>
          <input name="end_date" required type="date" defaultValue="2026-09-30" />
        </label>
        <label className="form-field full">
          <span>Assets</span>
          <input name="assets" required defaultValue="BTC, ETH" />
        </label>
        <label className="form-field">
          <span>LLM provider</span>
          <select name="llm_provider" defaultValue="mock">
            <option value="mock">mock</option>
            <option value="openai_compatible">openai_compatible</option>
          </select>
        </label>
        <label className="form-field">
          <span>Visibility</span>
          <select name="visibility" defaultValue="private">
            <option value="private">private</option>
            <option value="public">public</option>
          </select>
        </label>
        <label className="form-field">
          <span>LLM base URL</span>
          <input name="llm_base_url" placeholder="http://localhost:11434/v1" />
        </label>
        <label className="form-field">
          <span>LLM model</span>
          <input name="llm_model" placeholder="local-model-name" />
        </label>
      </div>
      <section className="stack">
        <h2>Agent groups</h2>
        <AgentSelector agents={agents} />
      </section>
      <button type="submit">Generate scenario</button>
    </form>
  );
}

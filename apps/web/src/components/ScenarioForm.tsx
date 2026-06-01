"use client";

import { AgentSelector } from "./AgentSelector";
import type { AgentProfile } from "@/lib/types";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

export function ScenarioForm({
  agents,
  action,
}: {
  agents: AgentProfile[];
  action: (formData: FormData) => Promise<void>;
}) {
  const { t } = useI18n();

  return (
    <form action={action} className="stack">
      <div className="form-grid">
        <label className="form-field full">
          <span>{t("scenarioCreate.formTitle")}</span>
          <input
            name="title"
            required
            defaultValue="2026 Q3 BTC ETH Daily Scenario"
          />
        </label>
        <label className="form-field full">
          <span>{t("scenarioCreate.formDescription")}</span>
          <textarea
            name="description"
            defaultValue="Local mock scenario rehearsal using daily association context."
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.startDate")}</span>
          <input name="start_date" required type="date" defaultValue="2026-07-01" />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.endDate")}</span>
          <input name="end_date" required type="date" defaultValue="2026-09-30" />
        </label>
        <label className="form-field full">
          <span>{t("scenarioCreate.assets")}</span>
          <input name="assets" required defaultValue="BTC, ETH" />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmProvider")}</span>
          <select name="llm_provider" defaultValue="mock">
            <option value="mock">{formatEnumLabel(t, "llm_provider", "mock")}</option>
            <option value="openai_compatible">
              {formatEnumLabel(t, "llm_provider", "openai_compatible")}
            </option>
          </select>
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.visibility")}</span>
          <select name="visibility" defaultValue="private">
            <option value="private">
              {formatEnumLabel(t, "visibility", "private")}
            </option>
            <option value="public">{formatEnumLabel(t, "visibility", "public")}</option>
          </select>
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmBaseUrl")}</span>
          <input name="llm_base_url" placeholder="http://localhost:11434/v1" />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmModel")}</span>
          <input name="llm_model" placeholder="local-model-name" />
        </label>
      </div>
      <section className="stack">
        <h2>{t("scenarioCreate.agentGroups")}</h2>
        <AgentSelector agents={agents} />
      </section>
      <button type="submit">{t("scenarioCreate.generate")}</button>
    </form>
  );
}

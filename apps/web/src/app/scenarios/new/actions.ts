"use server";

import { redirect } from "next/navigation";
import { createScenario } from "@/lib/api";
import type { LlmProvider, ReportLanguage, Visibility } from "@/lib/types";

function getString(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function optionalString(value: string): string | null {
  return value ? value : null;
}

function optionalNumber(value: string): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export async function createScenarioAction(formData: FormData): Promise<void> {
  const assets = getString(formData, "assets")
    .split(",")
    .map((asset) => asset.trim().toUpperCase())
    .filter(Boolean);
  const agentIds = formData
    .getAll("agent_ids")
    .map((value) => String(value))
    .filter(Boolean);
  const llmProvider = getString(formData, "llm_provider") as LlmProvider;
  const visibility = getString(formData, "visibility") as Visibility;
  const language = getString(formData, "language") as ReportLanguage;

  const report = await createScenario({
    title: getString(formData, "title"),
    description: optionalString(getString(formData, "description")),
    start_date: getString(formData, "start_date"),
    end_date: getString(formData, "end_date"),
    assets,
    agent_ids: agentIds,
    llm_provider: llmProvider || "mock",
    llm_real_enabled: formData.get("llm_real_enabled") === "on",
    llm_base_url: optionalString(getString(formData, "llm_base_url")),
    llm_model: optionalString(getString(formData, "llm_model")),
    llm_api_key: optionalString(getString(formData, "llm_api_key")),
    llm_timeout_seconds: optionalNumber(getString(formData, "llm_timeout_seconds")),
    llm_max_output_tokens: optionalNumber(getString(formData, "llm_max_output_tokens")),
    visibility: visibility || "private",
    mode: "daily_association_only",
    language: language || "en",
  });

  redirect(`/scenarios/${report.scenario_id}`);
}

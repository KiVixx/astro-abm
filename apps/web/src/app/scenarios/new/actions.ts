"use server";

import { redirect } from "next/navigation";
import { createScenario } from "@/lib/api";
import type { LlmProvider, Visibility } from "@/lib/types";

function getString(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function optionalString(value: string): string | null {
  return value ? value : null;
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

  const report = await createScenario({
    title: getString(formData, "title"),
    description: optionalString(getString(formData, "description")),
    start_date: getString(formData, "start_date"),
    end_date: getString(formData, "end_date"),
    assets,
    agent_ids: agentIds,
    llm_provider: llmProvider || "mock",
    llm_base_url: optionalString(getString(formData, "llm_base_url")),
    llm_model: optionalString(getString(formData, "llm_model")),
    visibility: visibility || "private",
    mode: "daily_association_only",
  });

  redirect(`/scenarios/${report.scenario_id}`);
}

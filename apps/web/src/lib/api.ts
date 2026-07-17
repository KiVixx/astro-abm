import type {
  AgentProfile,
  LlmPresetSaveRequest,
  LlmPresetSummary,
  LlmPresetTestResponse,
  LlmTestRequest,
  LlmTestResponse,
  MarketSeriesProfile,
  ScenarioCreateRequest,
  ScenarioLlmChunkRequest,
  ScenarioLlmChunkResponse,
  ScenarioReport,
  ScenarioSummary,
  ScenarioWorldlineChunkRequest,
  ScenarioWorldlineChunkResponse,
  ScenarioWorldlineRegenerateFromRequest,
  ScenarioWorldlineRegenerateFromResponse,
} from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
  }
}

export function getApiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_ASTRO_ABM_API_BASE_URL?.replace(/\/$/, "") ||
    DEFAULT_API_BASE_URL
  );
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // Keep status text when the API returns a non-JSON error.
    }
    throw new ApiError(detail || "API request failed", response.status);
  }

  return (await response.json()) as T;
}

export async function getAgents(): Promise<AgentProfile[]> {
  return apiFetch<AgentProfile[]>("/agents");
}

export async function getAssets(): Promise<MarketSeriesProfile[]> {
  return apiFetch<MarketSeriesProfile[]>("/assets");
}

export async function getLlmPresets(): Promise<LlmPresetSummary[]> {
  return apiFetch<LlmPresetSummary[]>("/llm/presets");
}

export async function createLlmPreset(
  payload: LlmPresetSaveRequest,
): Promise<LlmPresetSummary> {
  return apiFetch<LlmPresetSummary>("/llm/presets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateLlmPreset(
  presetId: string,
  payload: LlmPresetSaveRequest,
): Promise<LlmPresetSummary> {
  return apiFetch<LlmPresetSummary>(`/llm/presets/${encodeURIComponent(presetId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteLlmPreset(
  presetId: string,
): Promise<{ preset_id: string; deleted: boolean }> {
  return apiFetch(`/llm/presets/${encodeURIComponent(presetId)}`, { method: "DELETE" });
}

export async function testLlmPreset(presetId: string): Promise<LlmPresetTestResponse> {
  return apiFetch<LlmPresetTestResponse>(
    `/llm/presets/${encodeURIComponent(presetId)}/test`,
    { method: "POST", body: "{}" },
  );
}

export async function testLlmConnection(payload: LlmTestRequest): Promise<LlmTestResponse> {
  return apiFetch<LlmTestResponse>("/llm/test", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getScenarios(): Promise<ScenarioSummary[]> {
  return apiFetch<ScenarioSummary[]>("/scenarios");
}

export async function getScenario(
  scenarioId: string,
  options: { includeMarkdown?: boolean } = {},
): Promise<ScenarioReport> {
  const query = options.includeMarkdown === false ? "?include_markdown=false" : "";
  return apiFetch<ScenarioReport>(
    `/scenarios/${encodeURIComponent(scenarioId)}${query}`,
  );
}

export async function deleteScenario(
  scenarioId: string,
): Promise<{ scenario_id: string; deleted: boolean }> {
  return apiFetch<{ scenario_id: string; deleted: boolean }>(
    `/scenarios/${encodeURIComponent(scenarioId)}`,
    { method: "DELETE" },
  );
}

export async function createScenario(
  payload: ScenarioCreateRequest,
): Promise<ScenarioReport> {
  return apiFetch<ScenarioReport>("/scenarios", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function generateScenarioLlmChunk(
  scenarioId: string,
  payload: ScenarioLlmChunkRequest,
): Promise<ScenarioLlmChunkResponse> {
  return apiFetch<ScenarioLlmChunkResponse>(
    `/scenarios/${encodeURIComponent(scenarioId)}/llm-chunks`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function generateScenarioWorldlineChunk(
  scenarioId: string,
  payload: ScenarioWorldlineChunkRequest,
): Promise<ScenarioWorldlineChunkResponse> {
  return apiFetch<ScenarioWorldlineChunkResponse>(
    `/scenarios/${encodeURIComponent(scenarioId)}/worldline-chunks`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function regenerateScenarioWorldlineFromChunk(
  scenarioId: string,
  payload: ScenarioWorldlineRegenerateFromRequest,
): Promise<ScenarioWorldlineRegenerateFromResponse> {
  return apiFetch<ScenarioWorldlineRegenerateFromResponse>(
    `/scenarios/${encodeURIComponent(scenarioId)}/worldline/regenerate-from`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

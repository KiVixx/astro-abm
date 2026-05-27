import type {
  AgentProfile,
  ScenarioCreateRequest,
  ScenarioReport,
  ScenarioSummary,
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

export async function getScenarios(): Promise<ScenarioSummary[]> {
  return apiFetch<ScenarioSummary[]>("/scenarios");
}

export async function getScenario(scenarioId: string): Promise<ScenarioReport> {
  return apiFetch<ScenarioReport>(`/scenarios/${encodeURIComponent(scenarioId)}`);
}

export async function createScenario(
  payload: ScenarioCreateRequest,
): Promise<ScenarioReport> {
  return apiFetch<ScenarioReport>("/scenarios", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

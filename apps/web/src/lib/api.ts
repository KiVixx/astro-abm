import type {
  AgentProfile,
  AuthSessionResponse,
  LlmPresetSaveRequest,
  LlmPresetSummary,
  LlmPresetTestResponse,
  LlmTestRequest,
  LlmTestResponse,
  LoginRequest,
  CustomMarketSeriesCreateRequest,
  CustomMarketSeriesRecord,
  CustomMarketSeriesUpdateRequest,
  MarketSeriesProfile,
  MarketSeriesListResponse,
  MarketSeriesRefreshResponse,
  MarkSixDrawRecord,
  MarkSixAstroResearch,
  MarkSixMotionCondition,
  MarkSixMoonPhaseCondition,
  MarkSixLlmWorldlineRequest,
  MarkSixLlmWorldlineResponse,
  MarkSixLlmPromptPreview,
  MarkSixPublicLlmWorldlineRecord,
  MarkSixPublicLlmWorldlineSummary,
  MarkSixFrequency,
  MarkSixStatus,
  MarkSixWorldlineRequest,
  MarkSixWorldlineResponse,
  RegisterRequest,
  ScenarioCreateRequest,
  ScenarioExportEnvelope,
  ScenarioLlmChunkRequest,
  ScenarioLlmChunkResponse,
  ScenarioReport,
  ScenarioSummary,
  ScenarioWorldlineChunkRequest,
  ScenarioWorldlineChunkResponse,
  ScenarioWorldlineRegenerateFromRequest,
  ScenarioWorldlineRegenerateFromResponse,
} from "./types";

const DEFAULT_API_BASE_URL = "/api";
const DEFAULT_INTERNAL_API_ORIGIN = "http://127.0.0.1:8000";
let verifiedCsrfToken: string | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
  }
}

function formatApiErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== "object" || !("msg" in item)) {
        return [];
      }
      const message = String(item.msg || "").replace(/^Value error,\s*/i, "").trim();
      return message ? [message] : [];
    });
    return messages.length ? messages.join(" ") : null;
  }
  return null;
}

export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return (
      process.env.ASTRO_ABM_INTERNAL_API_ORIGIN?.replace(/\/$/, "") ||
      DEFAULT_INTERNAL_API_ORIGIN
    );
  }
  return (
    process.env.NEXT_PUBLIC_ASTRO_ABM_API_BASE_URL?.replace(/\/$/, "") ||
    DEFAULT_API_BASE_URL
  );
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const csrfToken = typeof document === "undefined" ? null : currentCsrfToken();
  const method = (init?.method || "GET").toUpperCase();
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken && !["GET", "HEAD", "OPTIONS"].includes(method)
        ? { "X-CSRF-Token": csrfToken }
        : {}),
      ...(init?.headers || {}),
    },
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = formatApiErrorDetail(body.detail) || detail;
    } catch {
      // Keep status text when the API returns a non-JSON error.
    }
    throw new ApiError(detail || "API request failed", response.status);
  }

  return (await response.json()) as T;
}

function readCookieValues(name: string): string[] {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie.split(";").map((item) => item.trim())
    .filter((item) => item.startsWith(prefix))
    .map((item) => decodeURIComponent(item.slice(prefix.length)));
}

function currentCsrfToken(): string | null {
  const cookies = readCookieValues("astro_abm_csrf");
  return (verifiedCsrfToken && cookies.includes(verifiedCsrfToken)
    ? verifiedCsrfToken : cookies.at(-1)) || null;
}

function rememberCsrfToken(token: string | null | undefined): void {
  if (typeof window !== "undefined") verifiedCsrfToken = token || null;
}

export async function getAuthSession(): Promise<AuthSessionResponse> {
  const session = await apiFetch<AuthSessionResponse>("/auth/me");
  rememberCsrfToken(session.csrf_token);
  return session;
}

export async function registerAccount(payload: RegisterRequest): Promise<AuthSessionResponse> {
  const session = await apiFetch<AuthSessionResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  rememberCsrfToken(session.csrf_token);
  return session;
}

export async function loginAccount(payload: LoginRequest): Promise<AuthSessionResponse> {
  const session = await apiFetch<AuthSessionResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  rememberCsrfToken(session.csrf_token);
  return session;
}

export async function logoutAccount(): Promise<{ logged_out: boolean }> {
  const result = await apiFetch<{ logged_out: boolean }>("/auth/logout", {
    method: "POST",
    body: "{}",
  });
  rememberCsrfToken(null);
  return result;
}

export async function claimGuestWorldlines(): Promise<{ claimed_worldline_count: number }> {
  return apiFetch<{ claimed_worldline_count: number }>("/auth/claim-guest-worldlines", {
    method: "POST",
    body: "{}",
  });
}

export async function exportScenario(scenarioId: string): Promise<ScenarioExportEnvelope> {
  return apiFetch<ScenarioExportEnvelope>(
    `/scenarios/${encodeURIComponent(scenarioId)}/export`,
  );
}

export async function importScenario(
  envelope: ScenarioExportEnvelope,
  visibility: "public" | "private",
): Promise<ScenarioReport> {
  return apiFetch<ScenarioReport>("/scenarios/import", {
    method: "POST",
    body: JSON.stringify({ envelope, visibility }),
  });
}

export async function getAgents(): Promise<AgentProfile[]> {
  return apiFetch<AgentProfile[]>("/agents");
}

export async function getAssets(cookieHeader?: string): Promise<MarketSeriesProfile[]> {
  return apiFetch<MarketSeriesProfile[]>("/assets", {
    headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
  });
}

export async function getMarketSeries(
  cookieHeader?: string,
): Promise<MarketSeriesListResponse> {
  return apiFetch<MarketSeriesListResponse>("/market-series", {
    headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
  });
}

export async function createMarketSeries(
  payload: CustomMarketSeriesCreateRequest,
): Promise<CustomMarketSeriesRecord> {
  return apiFetch<CustomMarketSeriesRecord>("/market-series", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateMarketSeries(
  seriesId: string,
  payload: CustomMarketSeriesUpdateRequest,
): Promise<CustomMarketSeriesRecord> {
  return apiFetch<CustomMarketSeriesRecord>(
    `/market-series/${encodeURIComponent(seriesId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export async function deleteMarketSeries(
  seriesId: string,
): Promise<{ series_id: string; deleted: boolean; price_history_retained: boolean }> {
  return apiFetch(`/market-series/${encodeURIComponent(seriesId)}`, {
    method: "DELETE",
  });
}

export async function validateMarketSeries(
  seriesId: string,
): Promise<MarketSeriesRefreshResponse> {
  return apiFetch<MarketSeriesRefreshResponse>(
    `/market-series/${encodeURIComponent(seriesId)}/validate`,
    { method: "POST", body: "{}" },
  );
}

export async function refreshMarketSeries(
  seriesId: string,
): Promise<MarketSeriesRefreshResponse> {
  return apiFetch<MarketSeriesRefreshResponse>(
    `/market-series/${encodeURIComponent(seriesId)}/refresh`,
    { method: "POST", body: "{}" },
  );
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

export async function getScenarios(cookieHeader?: string): Promise<ScenarioSummary[]> {
  return apiFetch<ScenarioSummary[]>("/scenarios", {
    headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
  });
}

export async function getScenario(
  scenarioId: string,
  options: { includeMarkdown?: boolean; cookieHeader?: string } = {},
): Promise<ScenarioReport> {
  const query = options.includeMarkdown === false ? "?include_markdown=false" : "";
  return apiFetch<ScenarioReport>(
    `/scenarios/${encodeURIComponent(scenarioId)}${query}`,
    { headers: options.cookieHeader ? { Cookie: options.cookieHeader } : undefined },
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

export async function getMarkSixStatus(): Promise<MarkSixStatus> {
  return apiFetch<MarkSixStatus>("/marksix/status");
}

export async function getMarkSixDraws(limit = 12): Promise<MarkSixDrawRecord[]> {
  return apiFetch<MarkSixDrawRecord[]>(`/marksix/draws?limit=${limit}`);
}

export async function getMarkSixFrequencies(): Promise<MarkSixFrequency[]> {
  return apiFetch<MarkSixFrequency[]>("/marksix/frequencies");
}

export async function getMarkSixAstroResearch(params: {
  contextType: "planet_motion" | "moon_phase";
  body: string;
  condition: MarkSixMotionCondition | MarkSixMoonPhaseCondition;
  numberRole: "main" | "extra";
}): Promise<MarkSixAstroResearch> {
  const query = new URLSearchParams({
    context_type: params.contextType,
    body: params.body,
    condition: params.condition,
    number_role: params.numberRole,
  });
  return apiFetch<MarkSixAstroResearch>(`/marksix/astro-research?${query.toString()}`);
}

export async function createMarkSixWorldlines(
  payload: MarkSixWorldlineRequest,
): Promise<MarkSixWorldlineResponse> {
  return apiFetch<MarkSixWorldlineResponse>("/marksix/worldlines", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createMarkSixLlmWorldline(
  payload: MarkSixLlmWorldlineRequest,
): Promise<MarkSixLlmWorldlineResponse> {
  return apiFetch<MarkSixLlmWorldlineResponse>("/marksix/llm-worldlines", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function previewMarkSixLlmPrompt(
  payload: MarkSixLlmWorldlineRequest,
): Promise<MarkSixLlmPromptPreview> {
  return apiFetch<MarkSixLlmPromptPreview>("/marksix/llm-prompt-preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getPublicMarkSixLlmWorldlines(
  limit = 50,
  offset = 0,
): Promise<MarkSixPublicLlmWorldlineSummary[]> {
  return apiFetch<MarkSixPublicLlmWorldlineSummary[]>(
    `/marksix/llm-worldlines?limit=${limit}&offset=${offset}`,
  );
}

export async function getPublicMarkSixLlmWorldline(
  libraryId: string,
): Promise<MarkSixPublicLlmWorldlineRecord> {
  return apiFetch<MarkSixPublicLlmWorldlineRecord>(
    `/marksix/llm-worldlines/${encodeURIComponent(libraryId)}`,
  );
}

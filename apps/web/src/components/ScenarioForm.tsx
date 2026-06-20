"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AgentSelector } from "./AgentSelector";
import { AssetSelector } from "./AssetSelector";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";
import type {
  AgentProfile,
  LlmProvider,
  MarketSeriesProfile,
  ReportLanguage,
  ScenarioCreateRequest,
  ScenarioLlmChunkRequest,
  ScenarioLlmChunkResponse,
  ScenarioReport,
  ScenarioWorldlineChunkRequest,
  ScenarioWorldlineChunkResponse,
  Visibility,
  WorldlineProvider,
} from "@/lib/types";

interface GenerationProgress {
  active: boolean;
  phase: "idle" | "base" | "llm" | "delay" | "done" | "error";
  currentChunk: number;
  totalChunks: number;
  message: string;
}

interface LlmSettingsPreset {
  id: string;
  name: string;
  createdAt: string;
  provider: LlmProvider;
  realEnabled: boolean;
  baseUrl: string;
  model: string;
  chunkSizeDays: string;
  callDelaySeconds: string;
  timeoutSeconds: string;
  maxOutputTokens: string;
  userPrompt: string;
  worldlineProvider?: WorldlineProvider;
  apiKey?: string | null;
}

const DEFAULT_LLM_PROVIDER: LlmProvider = "openai_compatible";
const DEFAULT_LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/";
const DEFAULT_LLM_MODEL = "gemini-3.5-flash";
const DEFAULT_LLM_CALL_DELAY_SECONDS = 2;
const LLM_PRESETS_STORAGE_KEY = "astro_abm_llm_presets_v1";

export function ScenarioForm({
  agents,
  marketSeries,
  createAction,
  chunkAction,
  worldlineChunkAction,
  product = "scenario",
}: {
  agents: AgentProfile[];
  marketSeries: MarketSeriesProfile[];
  createAction: (payload: ScenarioCreateRequest) => Promise<ScenarioReport>;
  chunkAction: (
    scenarioId: string,
    payload: ScenarioLlmChunkRequest,
  ) => Promise<ScenarioLlmChunkResponse>;
  worldlineChunkAction?: (
    scenarioId: string,
    payload: ScenarioWorldlineChunkRequest,
  ) => Promise<ScenarioWorldlineChunkResponse>;
  product?: "scenario" | "worldline";
}) {
  const router = useRouter();
  const { language: uiLanguage, t } = useI18n();
  const formRef = useRef<HTMLFormElement | null>(null);
  const [defaultDateRange] = useState(() => getDefaultScenarioDateRange());
  const [reportLanguage, setReportLanguage] = useState<ReportLanguage>(uiLanguage);
  const [hasManualLanguageOverride, setHasManualLanguageOverride] = useState(false);
  const [llmPresets, setLlmPresets] = useState<LlmSettingsPreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [presetName, setPresetName] = useState("Gemini default");
  const [includeApiKeyInPreset, setIncludeApiKeyInPreset] = useState(false);
  const [presetMessage, setPresetMessage] = useState("");
  const [progress, setProgress] = useState<GenerationProgress>({
    active: false,
    phase: "idle",
    currentChunk: 0,
    totalChunks: 0,
    message: "",
  });

  useEffect(() => {
    if (!hasManualLanguageOverride) {
      setReportLanguage(uiLanguage);
    }
  }, [hasManualLanguageOverride, uiLanguage]);

  useEffect(() => {
    setLlmPresets(loadLlmPresets());
  }, []);

  const progressPct =
    progress.totalChunks > 0
      ? Math.round((progress.currentChunk / progress.totalChunks) * 100)
      : progress.phase === "base"
        ? 10
        : progress.phase === "done"
          ? 100
          : 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload = payloadFromFormData(formData);
    const chunkSizeDays = clampNumber(
      optionalNumber(getString(formData, "llm_chunk_size_days")) ?? 3,
      1,
      5,
    ) as 1 | 2 | 3 | 5;
    const callDelaySeconds = clampNumber(
      optionalNumber(getString(formData, "llm_call_delay_seconds")) ??
        DEFAULT_LLM_CALL_DELAY_SECONDS,
      0,
      120,
    );
    const shouldChunkWorldline =
      product === "worldline" && payload.worldline_provider === "llm";
    const shouldChunkLlm =
      product !== "worldline" &&
      payload.llm_provider === "openai_compatible" && payload.llm_real_enabled === true;

    try {
      setProgress({
        active: true,
        phase: "base",
        currentChunk: 0,
        totalChunks: 0,
        message: t("scenarioCreate.progressBase"),
      });

      const basePayload: ScenarioCreateRequest = shouldChunkLlm || shouldChunkWorldline
        ? {
            ...payload,
            llm_provider: "mock",
            llm_real_enabled: false,
            llm_api_key: null,
            worldline_provider: "deterministic_mock",
          }
        : payload;
      const report = await createAction(basePayload);

      if (!shouldChunkLlm && !shouldChunkWorldline) {
        setProgress({
          active: true,
          phase: "done",
          currentChunk: 1,
          totalChunks: 1,
          message: t("scenarioCreate.progressComplete"),
        });
        router.push(
          `${product === "worldline" ? "/worldlines" : "/scenarios"}/${report.scenario_id}`,
        );
        return;
      }

      const chunks = buildDateChunks(payload.start_date, payload.end_date, chunkSizeDays);
      for (const [index, chunk] of chunks.entries()) {
        const chunkLabel = shouldChunkWorldline
          ? t("scenarioCreate.progressWorldlineChunk")
          : t("scenarioCreate.progressLlmChunk");
        setProgress({
          active: true,
          phase: "llm",
          currentChunk: index,
          totalChunks: chunks.length,
          message: `${chunkLabel} ${index + 1}/${chunks.length}: ${chunk.start} → ${chunk.end}`,
        });
        if (shouldChunkWorldline) {
          if (!worldlineChunkAction) {
            throw new Error("Worldline chunk action is not configured.");
          }
          const response = await worldlineChunkAction(report.scenario_id, {
            llm_provider: payload.llm_provider,
            llm_real_enabled: payload.llm_real_enabled,
            llm_base_url: payload.llm_base_url,
            llm_model: payload.llm_model,
            llm_api_key: payload.llm_api_key,
            llm_user_prompt: payload.llm_user_prompt,
            llm_timeout_seconds: payload.llm_timeout_seconds,
            llm_max_output_tokens: payload.llm_max_output_tokens,
            language: payload.language,
            chunk_start_date: chunk.start,
            chunk_end_date: chunk.end,
            chunk_index: index + 1,
            total_chunks: chunks.length,
            worldline_chunk_days: chunkSizeDays,
          });
          if (!["completed", "fallback", "dry_run"].includes(response.worldline_status)) {
            throw new Error(
              `${t("scenarioCreate.progressChunkFailed")}: ${response.worldline_status}`,
            );
          }
        } else {
          const response = await chunkAction(report.scenario_id, {
            llm_provider: payload.llm_provider,
            llm_real_enabled: payload.llm_real_enabled,
            llm_base_url: payload.llm_base_url,
            llm_model: payload.llm_model,
            llm_api_key: payload.llm_api_key,
            llm_user_prompt: payload.llm_user_prompt,
            llm_timeout_seconds: payload.llm_timeout_seconds,
            llm_max_output_tokens: payload.llm_max_output_tokens,
            language: payload.language,
            chunk_start_date: chunk.start,
            chunk_end_date: chunk.end,
            chunk_index: index + 1,
            total_chunks: chunks.length,
          });
          if (response.llm_status !== "completed") {
            throw new Error(`${t("scenarioCreate.progressChunkFailed")}: ${response.llm_status}`);
          }
        }
        setProgress({
          active: true,
          phase: "llm",
          currentChunk: index + 1,
          totalChunks: chunks.length,
          message: `${t("scenarioCreate.progressLlmChunkDone")} ${index + 1}/${chunks.length}`,
        });
        const hasNextChunk = index < chunks.length - 1;
        if (hasNextChunk && callDelaySeconds > 0) {
          setProgress({
            active: true,
            phase: "delay",
            currentChunk: index + 1,
            totalChunks: chunks.length,
            message: `${t("scenarioCreate.progressLlmDelay")} ${callDelaySeconds}s`,
          });
          await sleep(callDelaySeconds * 1000);
        }
      }

      setProgress({
        active: true,
        phase: "done",
        currentChunk: chunks.length,
        totalChunks: chunks.length,
        message: t("scenarioCreate.progressComplete"),
      });
      router.push(
        `${product === "worldline" ? "/worldlines" : "/scenarios"}/${report.scenario_id}`,
      );
    } catch (error) {
      setProgress({
        active: true,
        phase: "error",
        currentChunk: progress.currentChunk,
        totalChunks: progress.totalChunks,
        message: error instanceof Error ? error.message : t("common.unknownError"),
      });
    }
  }

  function saveCurrentLlmPreset() {
    const form = formRef.current;
    if (!form) {
      return;
    }
    const trimmedName = presetName.trim() || t("scenarioCreate.llmPresetUntitled");
    const nextPreset = readLlmPresetFromForm(form, trimmedName, includeApiKeyInPreset);
    const nextPresets = [
      nextPreset,
      ...llmPresets.filter((preset) => preset.name !== trimmedName),
    ].slice(0, 12);
    setLlmPresets(nextPresets);
    persistLlmPresets(nextPresets);
    setSelectedPresetId(nextPreset.id);
    setPresetMessage(
      includeApiKeyInPreset
        ? t("scenarioCreate.llmPresetSavedWithKey")
        : t("scenarioCreate.llmPresetSaved"),
    );
  }

  function recallSelectedLlmPreset() {
    const form = formRef.current;
    const preset = llmPresets.find((candidate) => candidate.id === selectedPresetId);
    if (!form || !preset) {
      return;
    }
    applyLlmPresetToForm(form, preset);
    setPresetName(preset.name);
    setIncludeApiKeyInPreset(Boolean(preset.apiKey));
    setPresetMessage(t("scenarioCreate.llmPresetRecalled"));
  }

  function deleteSelectedLlmPreset() {
    if (!selectedPresetId) {
      return;
    }
    const nextPresets = llmPresets.filter((preset) => preset.id !== selectedPresetId);
    setLlmPresets(nextPresets);
    persistLlmPresets(nextPresets);
    setSelectedPresetId("");
    setPresetMessage(t("scenarioCreate.llmPresetDeleted"));
  }

  return (
    <form className="stack" onSubmit={handleSubmit} ref={formRef}>
      {product === "worldline" ? (
        <section className="notice">
          <strong>{t("worldline.simulationMode")}: </strong>
          {t("worldline.deterministicMock")}
          <p>{t("worldline.modeHelp")}</p>
        </section>
      ) : null}
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
          <input name="start_date" required type="date" defaultValue={defaultDateRange.startDate} />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.endDate")}</span>
          <input name="end_date" required type="date" defaultValue={defaultDateRange.endDate} />
        </label>
        <div className="form-field full">
          <span>{t("scenarioCreate.marketSeries")}</span>
          <AssetSelector marketSeries={marketSeries} />
        </div>
        <label className="form-field">
          <span>{t("scenarioCreate.llmProvider")}</span>
          <select name="llm_provider" defaultValue={DEFAULT_LLM_PROVIDER}>
            <option value="mock">{formatEnumLabel(t, "llm_provider", "mock")}</option>
            <option value="openai_compatible">
              {formatEnumLabel(t, "llm_provider", "openai_compatible")}
            </option>
          </select>
        </label>
        {product === "worldline" ? (
          <label className="form-field">
            <span>{t("worldline.modeSelect")}</span>
            <select name="worldline_provider" defaultValue="deterministic_mock">
              <option value="deterministic_mock">{t("worldline.deterministicMock")}</option>
              <option value="llm">{t("worldline.llmChunk")}</option>
            </select>
            <span className="muted">{t("worldline.llmChunkHelp")}</span>
          </label>
        ) : null}
        <label className="checkbox-card">
          <input defaultChecked name="llm_real_enabled" type="checkbox" />
          <span>
            <strong>{t("scenarioCreate.llmRealEnabled")}</strong>
            <br />
            <span className="muted">{t("scenarioCreate.llmRealEnabledHelp")}</span>
          </span>
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
          <span>{t("scenarioCreate.reportLanguage")}</span>
          <select
            name="language"
            onChange={(event) => {
              setHasManualLanguageOverride(true);
              setReportLanguage(event.target.value as ReportLanguage);
            }}
            value={reportLanguage}
          >
            <option value="en">{formatEnumLabel(t, "report_language", "en")}</option>
            <option value="zh-Hant">
              {formatEnumLabel(t, "report_language", "zh-Hant")}
            </option>
          </select>
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmBaseUrl")}</span>
          <input
            defaultValue={DEFAULT_LLM_BASE_URL}
            name="llm_base_url"
            placeholder={DEFAULT_LLM_BASE_URL}
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmModel")}</span>
          <input
            defaultValue={DEFAULT_LLM_MODEL}
            name="llm_model"
            placeholder={DEFAULT_LLM_MODEL}
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmChunkSizeDays")}</span>
          <select name="llm_chunk_size_days" defaultValue="3">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="5">5</option>
          </select>
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmCallDelaySeconds")}</span>
          <input
            defaultValue={String(DEFAULT_LLM_CALL_DELAY_SECONDS)}
            max="120"
            min="0"
            name="llm_call_delay_seconds"
            step="0.5"
            type="number"
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmTimeoutSeconds")}</span>
          <input
            defaultValue="120"
            max="600"
            min="1"
            name="llm_timeout_seconds"
            step="1"
            type="number"
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmMaxOutputTokens")}</span>
          <input
            defaultValue="5000"
            max="32000"
            min="512"
            name="llm_max_output_tokens"
            step="1"
            type="number"
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmApiKey")}</span>
          <input
            autoComplete="off"
            name="llm_api_key"
            placeholder={t("scenarioCreate.llmApiKeyPlaceholder")}
            type="password"
          />
        </label>
        <label className="form-field full">
          <span>{t("scenarioCreate.llmUserPrompt")}</span>
          <textarea
            name="llm_user_prompt"
            placeholder={t("scenarioCreate.llmUserPromptPlaceholder")}
            rows={5}
          />
          <span className="muted">{t("scenarioCreate.llmUserPromptHelp")}</span>
        </label>
        <section className="llm-preset-panel full">
          <div>
            <h3>{t("scenarioCreate.llmPresetTitle")}</h3>
            <p className="muted">{t("scenarioCreate.llmPresetHelp")}</p>
          </div>
          <div className="llm-preset-grid">
            <label className="form-field">
              <span>{t("scenarioCreate.llmPresetName")}</span>
              <input
                onChange={(event) => setPresetName(event.target.value)}
                value={presetName}
              />
            </label>
            <label className="form-field">
              <span>{t("scenarioCreate.llmPresetRecall")}</span>
              <select
                onChange={(event) => setSelectedPresetId(event.target.value)}
                value={selectedPresetId}
              >
                <option value="">{t("scenarioCreate.llmPresetSelect")}</option>
                {llmPresets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="checkbox-card compact">
            <input
              checked={includeApiKeyInPreset}
              onChange={(event) => setIncludeApiKeyInPreset(event.target.checked)}
              type="checkbox"
            />
            <span>
              <strong>{t("scenarioCreate.llmPresetIncludeApiKey")}</strong>
              <br />
              <span className="muted">{t("scenarioCreate.llmPresetApiKeyWarning")}</span>
            </span>
          </label>
          <div className="button-row">
            <button className="button secondary" onClick={saveCurrentLlmPreset} type="button">
              {t("scenarioCreate.llmPresetSave")}
            </button>
            <button
              className="button secondary"
              disabled={!selectedPresetId}
              onClick={recallSelectedLlmPreset}
              type="button"
            >
              {t("scenarioCreate.llmPresetRecallButton")}
            </button>
            <button
              className="button secondary"
              disabled={!selectedPresetId}
              onClick={deleteSelectedLlmPreset}
              type="button"
            >
              {t("scenarioCreate.llmPresetDelete")}
            </button>
          </div>
          {presetMessage ? <p className="muted">{presetMessage}</p> : null}
        </section>
        <div className="notice full">
          <p>{t("scenarioCreate.llmApiKeyNote")}</p>
          <p>{t("scenarioCreate.realLlmEnablementNote")}</p>
        </div>
      </div>
      <section className="stack">
        <h2>{t("scenarioCreate.agentGroups")}</h2>
        <AgentSelector agents={agents} />
      </section>
      <button disabled={progress.active && progress.phase !== "error"} type="submit">
        {progress.active && progress.phase !== "error"
          ? t("scenarioCreate.generating")
          : product === "worldline"
            ? t("worldline.generate")
            : t("scenarioCreate.generate")}
      </button>
      {progress.active ? (
        <section className={`notice scenario-progress ${progress.phase}`}>
          <div className="scenario-progress-header">
            <strong>{t("scenarioCreate.progressTitle")}</strong>
            <span>{progressPct}%</span>
          </div>
          <div className="scenario-progress-bar" aria-hidden="true">
            <div style={{ width: `${progressPct}%` }} />
          </div>
          <p>{progress.message}</p>
        </section>
      ) : null}
    </form>
  );
}

function payloadFromFormData(formData: FormData): ScenarioCreateRequest {
  const assets = getString(formData, "assets")
    .split(",")
    .map((asset) => asset.trim().toUpperCase())
    .filter(Boolean);
  const agentIds = formData
    .getAll("agent_ids")
    .map((value) => String(value))
    .filter(Boolean);
  return {
    title: getString(formData, "title"),
    description: optionalString(getString(formData, "description")),
    start_date: getString(formData, "start_date"),
    end_date: getString(formData, "end_date"),
    assets,
    agent_ids: agentIds,
    llm_provider: (getString(formData, "llm_provider") || DEFAULT_LLM_PROVIDER) as LlmProvider,
    llm_real_enabled: formData.get("llm_real_enabled") === "on",
    llm_base_url: optionalString(getString(formData, "llm_base_url")),
    llm_model: optionalString(getString(formData, "llm_model")),
    llm_api_key: optionalString(getString(formData, "llm_api_key")),
    llm_user_prompt: optionalString(getString(formData, "llm_user_prompt")),
    llm_timeout_seconds: optionalNumber(getString(formData, "llm_timeout_seconds")),
    llm_max_output_tokens: optionalNumber(getString(formData, "llm_max_output_tokens")),
    visibility: (getString(formData, "visibility") || "private") as Visibility,
    mode: "daily_association_only",
    language: (getString(formData, "language") || "en") as ReportLanguage,
    worldline_provider: (
      getString(formData, "worldline_provider") || "deterministic_mock"
    ) as WorldlineProvider,
    worldline_chunk_days: clampNumber(
      optionalNumber(getString(formData, "llm_chunk_size_days")) ?? 3,
      1,
      5,
    ) as 1 | 2 | 3 | 5,
  };
}

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

function buildDateChunks(startDate: string, endDate: string, chunkSizeDays: number) {
  const chunks: Array<{ start: string; end: string }> = [];
  let current = parseDate(startDate);
  const end = parseDate(endDate);
  while (current <= end) {
    const chunkStart = current;
    const chunkEnd = new Date(current);
    chunkEnd.setUTCDate(chunkEnd.getUTCDate() + chunkSizeDays - 1);
    if (chunkEnd > end) {
      chunkEnd.setTime(end.getTime());
    }
    chunks.push({ start: formatDate(chunkStart), end: formatDate(chunkEnd) });
    current = new Date(chunkEnd);
    current.setUTCDate(current.getUTCDate() + 1);
  }
  return chunks;
}

function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}

function formatDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getDefaultScenarioDateRange() {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 29);
  return {
    startDate: formatLocalDate(start),
    endDate: formatLocalDate(end),
  };
}

function formatLocalDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function loadLlmPresets(): LlmSettingsPreset[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(LLM_PRESETS_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isLlmSettingsPreset);
  } catch {
    return [];
  }
}

function persistLlmPresets(presets: LlmSettingsPreset[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(LLM_PRESETS_STORAGE_KEY, JSON.stringify(presets));
}

function readLlmPresetFromForm(
  form: HTMLFormElement,
  name: string,
  includeApiKey: boolean,
): LlmSettingsPreset {
  const formData = new FormData(form);
  return {
    id: `llm_${Date.now().toString(36)}`,
    name,
    createdAt: new Date().toISOString(),
    provider: (getString(formData, "llm_provider") || DEFAULT_LLM_PROVIDER) as LlmProvider,
    realEnabled: formData.get("llm_real_enabled") === "on",
    baseUrl: getString(formData, "llm_base_url"),
    model: getString(formData, "llm_model"),
    chunkSizeDays: getString(formData, "llm_chunk_size_days") || "3",
    callDelaySeconds:
      getString(formData, "llm_call_delay_seconds") ||
      String(DEFAULT_LLM_CALL_DELAY_SECONDS),
    timeoutSeconds: getString(formData, "llm_timeout_seconds") || "120",
    maxOutputTokens: getString(formData, "llm_max_output_tokens") || "5000",
    userPrompt: getString(formData, "llm_user_prompt"),
    worldlineProvider: (getString(formData, "worldline_provider") ||
      "deterministic_mock") as WorldlineProvider,
    apiKey: includeApiKey ? getString(formData, "llm_api_key") : null,
  };
}

function applyLlmPresetToForm(form: HTMLFormElement, preset: LlmSettingsPreset) {
  setFormValue(form, "llm_provider", preset.provider);
  setFormChecked(form, "llm_real_enabled", preset.realEnabled);
  setFormValue(form, "llm_base_url", preset.baseUrl);
  setFormValue(form, "llm_model", preset.model);
  setFormValue(form, "llm_chunk_size_days", preset.chunkSizeDays);
  setFormValue(
    form,
    "llm_call_delay_seconds",
    preset.callDelaySeconds || String(DEFAULT_LLM_CALL_DELAY_SECONDS),
  );
  setFormValue(form, "llm_timeout_seconds", preset.timeoutSeconds);
  setFormValue(form, "llm_max_output_tokens", preset.maxOutputTokens);
  setFormValue(form, "llm_user_prompt", preset.userPrompt || "");
  setFormValue(form, "worldline_provider", preset.worldlineProvider || "deterministic_mock");
  setFormValue(form, "llm_api_key", preset.apiKey || "");
}

function setFormValue(form: HTMLFormElement, name: string, value: string) {
  const control = form.elements.namedItem(name);
  if (
    control instanceof HTMLInputElement ||
    control instanceof HTMLSelectElement ||
    control instanceof HTMLTextAreaElement
  ) {
    control.value = value;
  }
}

function setFormChecked(form: HTMLFormElement, name: string, checked: boolean) {
  const control = form.elements.namedItem(name);
  if (control instanceof HTMLInputElement) {
    control.checked = checked;
  }
}

function isLlmSettingsPreset(value: unknown): value is LlmSettingsPreset {
  if (!value || typeof value !== "object") {
    return false;
  }
  const preset = value as Partial<LlmSettingsPreset>;
  return (
    typeof preset.id === "string" &&
    typeof preset.name === "string" &&
    typeof preset.createdAt === "string" &&
    (preset.provider === "mock" || preset.provider === "openai_compatible") &&
    typeof preset.realEnabled === "boolean" &&
    typeof preset.baseUrl === "string" &&
    typeof preset.model === "string" &&
    typeof preset.chunkSizeDays === "string" &&
    (preset.callDelaySeconds === undefined || typeof preset.callDelaySeconds === "string") &&
    typeof preset.timeoutSeconds === "string" &&
    typeof preset.maxOutputTokens === "string" &&
    (preset.userPrompt === undefined || typeof preset.userPrompt === "string") &&
    (preset.worldlineProvider === undefined ||
      preset.worldlineProvider === "deterministic_mock" ||
      preset.worldlineProvider === "llm") &&
    (preset.apiKey === undefined ||
      preset.apiKey === null ||
      typeof preset.apiKey === "string")
  );
}

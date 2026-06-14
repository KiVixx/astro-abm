"use client";

import { useEffect, useState, type FormEvent } from "react";
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
  Visibility,
} from "@/lib/types";

interface GenerationProgress {
  active: boolean;
  phase: "idle" | "base" | "llm" | "done" | "error";
  currentChunk: number;
  totalChunks: number;
  message: string;
}

export function ScenarioForm({
  agents,
  marketSeries,
  createAction,
  chunkAction,
}: {
  agents: AgentProfile[];
  marketSeries: MarketSeriesProfile[];
  createAction: (payload: ScenarioCreateRequest) => Promise<ScenarioReport>;
  chunkAction: (
    scenarioId: string,
    payload: ScenarioLlmChunkRequest,
  ) => Promise<ScenarioLlmChunkResponse>;
}) {
  const router = useRouter();
  const { language: uiLanguage, t } = useI18n();
  const [reportLanguage, setReportLanguage] = useState<ReportLanguage>(uiLanguage);
  const [hasManualLanguageOverride, setHasManualLanguageOverride] = useState(false);
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
      3,
    );
    const shouldChunkLlm =
      payload.llm_provider === "openai_compatible" && payload.llm_real_enabled === true;

    try {
      setProgress({
        active: true,
        phase: "base",
        currentChunk: 0,
        totalChunks: 0,
        message: t("scenarioCreate.progressBase"),
      });

      const basePayload: ScenarioCreateRequest = shouldChunkLlm
        ? {
            ...payload,
            llm_provider: "mock",
            llm_real_enabled: false,
            llm_api_key: null,
          }
        : payload;
      const report = await createAction(basePayload);

      if (!shouldChunkLlm) {
        setProgress({
          active: true,
          phase: "done",
          currentChunk: 1,
          totalChunks: 1,
          message: t("scenarioCreate.progressComplete"),
        });
        router.push(`/scenarios/${report.scenario_id}`);
        return;
      }

      const chunks = buildDateChunks(payload.start_date, payload.end_date, chunkSizeDays);
      for (const [index, chunk] of chunks.entries()) {
        setProgress({
          active: true,
          phase: "llm",
          currentChunk: index,
          totalChunks: chunks.length,
          message: `${t("scenarioCreate.progressLlmChunk")} ${index + 1}/${chunks.length}: ${chunk.start} → ${chunk.end}`,
        });
        const response = await chunkAction(report.scenario_id, {
          llm_provider: payload.llm_provider,
          llm_real_enabled: payload.llm_real_enabled,
          llm_base_url: payload.llm_base_url,
          llm_model: payload.llm_model,
          llm_api_key: payload.llm_api_key,
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
        setProgress({
          active: true,
          phase: "llm",
          currentChunk: index + 1,
          totalChunks: chunks.length,
          message: `${t("scenarioCreate.progressLlmChunkDone")} ${index + 1}/${chunks.length}`,
        });
      }

      setProgress({
        active: true,
        phase: "done",
        currentChunk: chunks.length,
        totalChunks: chunks.length,
        message: t("scenarioCreate.progressComplete"),
      });
      router.push(`/scenarios/${report.scenario_id}`);
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

  return (
    <form className="stack" onSubmit={handleSubmit}>
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
        <div className="form-field full">
          <span>{t("scenarioCreate.marketSeries")}</span>
          <AssetSelector marketSeries={marketSeries} />
        </div>
        <label className="form-field">
          <span>{t("scenarioCreate.llmProvider")}</span>
          <select name="llm_provider" defaultValue="mock">
            <option value="mock">{formatEnumLabel(t, "llm_provider", "mock")}</option>
            <option value="openai_compatible">
              {formatEnumLabel(t, "llm_provider", "openai_compatible")}
            </option>
          </select>
        </label>
        <label className="checkbox-card">
          <input name="llm_real_enabled" type="checkbox" />
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
          <input name="llm_base_url" placeholder="http://localhost:11434/v1" />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmModel")}</span>
          <input name="llm_model" placeholder="local-model-name" />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.llmChunkSizeDays")}</span>
          <select name="llm_chunk_size_days" defaultValue="3">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
          </select>
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
    llm_provider: (getString(formData, "llm_provider") || "mock") as LlmProvider,
    llm_real_enabled: formData.get("llm_real_enabled") === "on",
    llm_base_url: optionalString(getString(formData, "llm_base_url")),
    llm_model: optionalString(getString(formData, "llm_model")),
    llm_api_key: optionalString(getString(formData, "llm_api_key")),
    llm_timeout_seconds: optionalNumber(getString(formData, "llm_timeout_seconds")),
    llm_max_output_tokens: optionalNumber(getString(formData, "llm_max_output_tokens")),
    visibility: (getString(formData, "visibility") || "private") as Visibility,
    mode: "daily_association_only",
    language: (getString(formData, "language") || "en") as ReportLanguage,
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

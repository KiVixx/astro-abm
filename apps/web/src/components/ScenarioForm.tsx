"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  createScenario,
  createLlmPreset,
  deleteLlmPreset,
  generateScenarioLlmChunk,
  generateScenarioWorldlineChunk,
  testLlmConnection,
  testLlmPreset,
  updateLlmPreset,
} from "@/lib/api";
import { AgentSelector } from "./AgentSelector";
import { AssetSelector } from "./AssetSelector";
import {
  LlmConnectionTestResult,
  type LlmConnectionFeedback,
} from "./LlmConnectionTestResult";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";
import { useLeaveWarning } from "@/lib/useLeaveWarning";
import type {
  AgentProfile,
  LlmProvider,
  LlmPresetSaveRequest,
  LlmPresetSummary,
  MarketSeriesProfile,
  ReportLanguage,
  ScenarioCreateRequest,
  ScenarioReport,
  Visibility,
  WorldlineProvider,
} from "@/lib/types";

interface GenerationProgress {
  active: boolean;
  phase: "idle" | "base" | "llm" | "delay" | "done" | "halted" | "error";
  currentChunk: number;
  totalChunks: number;
  message: string;
  savedReportPath?: string;
}

const DEFAULT_LLM_PROVIDER: LlmProvider = "openai_compatible";
const DEFAULT_LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/";
const DEFAULT_LLM_MODEL = "gemini-3.5-flash-thinking";
const DEFAULT_LLM_CHUNK_SIZE_DAYS = 1;
const DEFAULT_LLM_CALL_DELAY_SECONDS = 6;
const DEFAULT_LLM_MAX_OUTPUT_TOKENS = 32000;

export function ScenarioForm({
  agents,
  marketSeries,
  initialLlmPresets = [],
  product = "scenario",
}: {
  agents: AgentProfile[];
  marketSeries: MarketSeriesProfile[];
  initialLlmPresets?: LlmPresetSummary[];
  product?: "scenario" | "worldline";
}) {
  const router = useRouter();
  const { language: uiLanguage, t } = useI18n();
  const formRef = useRef<HTMLFormElement | null>(null);
  const [defaultDateRange] = useState(() => getDefaultScenarioDateRange());
  const [startDate, setStartDate] = useState(defaultDateRange.startDate);
  const [endDate, setEndDate] = useState(defaultDateRange.endDate);
  const [chunkSizeDays, setChunkSizeDays] = useState(DEFAULT_LLM_CHUNK_SIZE_DAYS);
  const [title, setTitle] = useState(() => getDefaultScenarioTitle(uiLanguage));
  const [description, setDescription] = useState(() => getDefaultScenarioDescription(uiLanguage));
  const [hasEditedTitle, setHasEditedTitle] = useState(false);
  const [hasEditedDescription, setHasEditedDescription] = useState(false);
  const [reportLanguage, setReportLanguage] = useState<ReportLanguage>(uiLanguage);
  const [hasManualLanguageOverride, setHasManualLanguageOverride] = useState(false);
  const [llmPresets, setLlmPresets] = useState<LlmPresetSummary[]>(initialLlmPresets);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [presetName, setPresetName] = useState("Gemini default");
  const [includeApiKeyInPreset, setIncludeApiKeyInPreset] = useState(false);
  const [presetMessage, setPresetMessage] = useState("");
  const [connectionFeedback, setConnectionFeedback] =
    useState<LlmConnectionFeedback | null>(null);
  const [llmProvider, setLlmProvider] = useState<LlmProvider>(DEFAULT_LLM_PROVIDER);
  const [worldlineProvider, setWorldlineProvider] =
    useState<WorldlineProvider>("deterministic_mock");
  const [realLlmEnabled, setRealLlmEnabled] = useState(true);
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
    if (!hasEditedTitle) {
      setTitle(getDefaultScenarioTitle(uiLanguage));
    }
    if (!hasEditedDescription) {
      setDescription(getDefaultScenarioDescription(uiLanguage));
    }
  }, [hasEditedDescription, hasEditedTitle, uiLanguage]);

  const progressPct =
    progress.totalChunks > 0
      ? Math.min(
          100,
          10 + Math.round((progress.currentChunk / progress.totalChunks) * 90),
        )
      : progress.phase === "base"
        ? 10
        : progress.phase === "done"
          ? 100
          : 0;
  const realLlmCanCall = llmProvider === "openai_compatible" && realLlmEnabled;
  const willCallLlm = realLlmCanCall;
  const plannedDayCount = inclusiveDateCount(startDate, endDate);
  const hasCompleteDateRange = Boolean(startDate && endDate);
  const dateRangeValid = hasCompleteDateRange && plannedDayCount > 0;
  const dateRangeOrderInvalid = hasCompleteDateRange && plannedDayCount === 0;
  const estimatedChunkCount = !willCallLlm || plannedDayCount === 0
    ? 0
    : product === "worldline" && worldlineProvider !== "llm"
      ? 1
      : Math.ceil(plannedDayCount / chunkSizeDays);
  const generationInProgress = progress.active
    && !["done", "halted", "error"].includes(progress.phase);
  useLeaveWarning(generationInProgress);
  const reportNarrativeLabel =
    product === "worldline" && worldlineProvider === "llm"
      ? t("scenarioCreate.callPlanReportMockDuringWorldline")
      : realLlmCanCall
        ? t("scenarioCreate.callPlanReportLlm")
        : t("scenarioCreate.callPlanReportMock");
  const worldlinePlaybackLabel =
    product === "worldline"
      ? worldlineProvider === "llm"
        ? realLlmCanCall
          ? t("scenarioCreate.callPlanWorldlineLlm")
          : t("scenarioCreate.callPlanWorldlineDryRun")
        : t("scenarioCreate.callPlanWorldlineMock")
      : t("scenarioCreate.callPlanWorldlineNotUsed");
  const realCallLabel = willCallLlm
    ? t("scenarioCreate.callPlanWillCall")
    : t("scenarioCreate.callPlanNoCall");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload = payloadFromFormData(formData);
    const chunkSizeDays = clampNumber(
      optionalNumber(getString(formData, "llm_chunk_size_days")) ??
        DEFAULT_LLM_CHUNK_SIZE_DAYS,
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
      product === "worldline" &&
      payload.worldline_provider === "llm" &&
      payload.llm_provider === "openai_compatible" &&
      payload.llm_real_enabled === true;
    const shouldChunkLlm =
      product !== "worldline" &&
      payload.llm_provider === "openai_compatible" && payload.llm_real_enabled === true;
    let savedReportPath: string | undefined;
    let processedChunks = 0;
    let plannedChunks = 0;

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
            llm_preset_id: null,
            llm_real_enabled: false,
            llm_api_key: null,
            worldline_provider: "deterministic_mock",
          }
        : payload;
      const report = await createScenario(basePayload);
      savedReportPath = `${product === "worldline" ? "/worldlines" : "/scenarios"}/${report.scenario_id}`;

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
      plannedChunks = chunks.length;
      let consecutiveWorldlineFailures = 0;
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
        let networkCallPerformed = false;
        if (shouldChunkWorldline) {
          const response = await generateScenarioWorldlineChunk(report.scenario_id, {
            llm_provider: payload.llm_provider,
            llm_preset_id: payload.llm_preset_id,
            llm_real_enabled: payload.llm_real_enabled,
            llm_base_url: payload.llm_base_url,
            llm_model: payload.llm_model,
            llm_api_key: payload.llm_api_key,
            llm_user_prompt: payload.llm_user_prompt,
            llm_timeout_seconds: payload.llm_timeout_seconds,
            llm_max_output_tokens: payload.llm_max_output_tokens,
            llm_call_delay_seconds: callDelaySeconds,
            language: payload.language,
            chunk_start_date: chunk.start,
            chunk_end_date: chunk.end,
            chunk_index: index + 1,
            total_chunks: chunks.length,
            worldline_chunk_days: chunkSizeDays,
          });
          processedChunks = index + 1;
          networkCallPerformed = worldlineChunkPerformedNetworkCall(
            response.report,
            index + 1,
          );
          if (!["completed", "fallback", "dry_run", "halted"].includes(response.worldline_status)) {
            throw new Error(
              `${t("scenarioCreate.progressChunkFailed")}: ${response.worldline_status}`,
            );
          }
          if (response.worldline_status === "dry_run") {
            setProgress({
              active: true,
              phase: "done",
              currentChunk: index + 1,
              totalChunks: chunks.length,
              message: t("scenarioCreate.progressWorldlineDryRunComplete"),
            });
            router.push(`/worldlines/${report.scenario_id}`);
            return;
          }
          consecutiveWorldlineFailures =
            response.worldline_status === "fallback"
              ? response.consecutive_failed_chunk_count || consecutiveWorldlineFailures + 1
              : response.worldline_status === "completed"
                ? 0
                : consecutiveWorldlineFailures;
          if (response.generation_halted || consecutiveWorldlineFailures >= 1) {
            setProgress({
              active: true,
              phase: "halted",
              currentChunk: index + 1,
              totalChunks: chunks.length,
              message: t("scenarioCreate.progressWorldlineHalted"),
            });
            await sleep(1200);
            router.push(`/worldlines/${report.scenario_id}`);
            return;
          }
        } else {
          const response = await generateScenarioLlmChunk(report.scenario_id, {
            llm_provider: payload.llm_provider,
            llm_preset_id: payload.llm_preset_id,
            llm_real_enabled: payload.llm_real_enabled,
            llm_base_url: payload.llm_base_url,
            llm_model: payload.llm_model,
            llm_api_key: payload.llm_api_key,
            llm_user_prompt: payload.llm_user_prompt,
            llm_timeout_seconds: payload.llm_timeout_seconds,
            llm_max_output_tokens: payload.llm_max_output_tokens,
            llm_call_delay_seconds: callDelaySeconds,
            language: payload.language,
            chunk_start_date: chunk.start,
            chunk_end_date: chunk.end,
            chunk_index: index + 1,
            total_chunks: chunks.length,
          });
          processedChunks = index + 1;
          networkCallPerformed = Boolean(
            response.report.llm_report?.provenance.network_call_performed,
          );
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
        if (hasNextChunk && callDelaySeconds > 0 && networkCallPerformed) {
          await waitForNextChunk({
            completedChunks: index + 1,
            delaySeconds: callDelaySeconds,
            nextChunk: chunks[index + 1],
            setProgress,
            totalChunks: chunks.length,
            waitingLabel: t("scenarioCreate.progressLlmDelay"),
            nextChunkLabel: t("scenarioCreate.progressNextChunk"),
          });
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
        currentChunk: processedChunks,
        totalChunks: plannedChunks,
        message: error instanceof Error ? error.message : t("common.unknownError"),
        savedReportPath,
      });
    }
  }

  async function saveCurrentLlmPreset() {
    const form = formRef.current;
    if (!form) {
      return;
    }
    const trimmedName = presetName.trim() || t("scenarioCreate.llmPresetUntitled");
    try {
      const payload = readLlmPresetFromForm(form, trimmedName, includeApiKeyInPreset);
      const existing = llmPresets.find((preset) => preset.preset_id === selectedPresetId);
      const saved = existing
        ? await updateLlmPreset(existing.preset_id, payload)
        : await createLlmPreset(payload);
      const nextPresets = [saved, ...llmPresets.filter((preset) => preset.preset_id !== saved.preset_id)];
      setLlmPresets(nextPresets);
      setSelectedPresetId(saved.preset_id);
      setPresetMessage(
        saved.has_api_key
          ? t("scenarioCreate.llmPresetSavedWithKey")
          : t("scenarioCreate.llmPresetSaved"),
      );
      setFormValue(form, "llm_api_key", "");
    } catch (error) {
      setPresetMessage(error instanceof Error ? error.message : t("common.unknownError"));
    }
  }

  function recallSelectedLlmPreset() {
    const form = formRef.current;
    const preset = llmPresets.find((candidate) => candidate.preset_id === selectedPresetId);
    if (!form || !preset) {
      return;
    }
    applyLlmPresetToForm(form, preset);
    setPresetName(preset.name);
    setIncludeApiKeyInPreset(preset.has_api_key);
    setLlmProvider(preset.provider);
    setWorldlineProvider((preset.worldline_provider as WorldlineProvider) || "deterministic_mock");
    setChunkSizeDays(normalizePresetChunkSize(preset.chunk_size_days));
    setRealLlmEnabled(preset.real_enabled);
    setPresetMessage(t("scenarioCreate.llmPresetRecalled"));
  }

  async function deleteSelectedLlmPreset() {
    if (!selectedPresetId) {
      return;
    }
    try {
      await deleteLlmPreset(selectedPresetId);
      setLlmPresets((current) => current.filter((preset) => preset.preset_id !== selectedPresetId));
      setSelectedPresetId("");
      setPresetMessage(t("scenarioCreate.llmPresetDeleted"));
    } catch (error) {
      setPresetMessage(error instanceof Error ? error.message : t("common.unknownError"));
    }
  }

  async function testCurrentLlmConnection() {
    const form = formRef.current;
    if (!form) return;
    const formData = new FormData(form);
    const selectedPreset = llmPresets.find((preset) => preset.preset_id === selectedPresetId);
    const baseUrl = getString(formData, "llm_base_url");
    const model = getString(formData, "llm_model");
    const apiKey = getString(formData, "llm_api_key");
    const matchesSelectedPreset = Boolean(
      selectedPreset
      && !apiKey
      && (selectedPreset.base_url || "") === baseUrl
      && (selectedPreset.model || "") === model,
    );
    setConnectionFeedback({ message: "", reachable: false, status: "testing", testing: true });
    try {
      const result = matchesSelectedPreset && selectedPreset
        ? await testLlmPreset(selectedPreset.preset_id)
        : await testLlmConnection({
            provider: (getString(formData, "llm_provider") || DEFAULT_LLM_PROVIDER) as LlmProvider,
            real_enabled: formData.get("llm_real_enabled") === "on",
            base_url: optionalString(baseUrl),
            model: optionalString(model),
            api_key: optionalString(apiKey),
            timeout_seconds: optionalNumber(getString(formData, "llm_timeout_seconds")),
            max_output_tokens: optionalNumber(getString(formData, "llm_max_output_tokens")),
          });
      setConnectionFeedback({
        message: result.message,
        reachable: result.reachable,
        status: result.status,
      });
    } catch (error) {
      setConnectionFeedback({
        message: error instanceof Error ? error.message : t("common.unknownError"),
        reachable: false,
        status: "request_failed",
      });
    }
  }

  return (
    <form
      className="stack scenario-form"
      onChange={(event) => {
        const target = event.target;
        if (
          !(target instanceof HTMLInputElement)
          && !(target instanceof HTMLSelectElement)
          && !(target instanceof HTMLTextAreaElement)
        ) return;
        const name = target.name;
        if (name.startsWith("llm_") || name === "worldline_provider") {
          setConnectionFeedback(null);
        }
      }}
      onSubmit={handleSubmit}
      ref={formRef}
    >
      {product === "worldline" ? (
        <section className="notice worldline-mode-notice">
          <span className="worldline-mode-signal" aria-hidden="true" />
          <div>
          <strong>{t("worldline.simulationMode")}: </strong>
          {worldlinePlaybackLabel}
          <p>{t("worldline.modeHelp")}</p>
          </div>
        </section>
      ) : null}
      <section className="form-section scenario-core-settings">
        <div className="form-section-heading">
          <span className="form-section-index" aria-hidden="true">01</span>
          <div>
          <h2>{t("scenarioCreate.basicSettings")}</h2>
          <p className="muted">{t("scenarioCreate.basicSettingsHelp")}</p>
          </div>
        </div>
      <div className="form-grid">
        <label className="form-field full">
          <span>{t("scenarioCreate.formTitle")}</span>
          <input
            name="title"
            required
            onChange={(event) => {
              setHasEditedTitle(true);
              setTitle(event.target.value);
            }}
            value={title}
          />
        </label>
        <label className="form-field full">
          <span>{t("scenarioCreate.formDescription")}</span>
          <textarea
            name="description"
            onChange={(event) => {
              setHasEditedDescription(true);
              setDescription(event.target.value);
            }}
            value={description}
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.startDate")}</span>
          <input
            aria-describedby={dateRangeOrderInvalid ? "scenario-date-range-error" : undefined}
            aria-invalid={dateRangeOrderInvalid || undefined}
            max={endDate || undefined}
            name="start_date"
            onChange={(event) => setStartDate(event.target.value)}
            required
            type="date"
            value={startDate}
          />
        </label>
        <label className="form-field">
          <span>{t("scenarioCreate.endDate")}</span>
          <input
            aria-describedby={dateRangeOrderInvalid ? "scenario-date-range-error" : undefined}
            aria-invalid={dateRangeOrderInvalid || undefined}
            min={startDate || undefined}
            name="end_date"
            onChange={(event) => setEndDate(event.target.value)}
            required
            type="date"
            value={endDate}
          />
        </label>
        {dateRangeOrderInvalid ? (
          <p className="notice warning full" id="scenario-date-range-error" role="alert">
            {t("scenarioCreate.dateRangeInvalid")}
          </p>
        ) : null}
        <div className="form-field full">
          <span>{t("scenarioCreate.marketSeries")}</span>
          <AssetSelector marketSeries={marketSeries} />
        </div>
        <label className="form-field">
          <span>{t("scenarioCreate.llmProvider")}</span>
          <select
            name="llm_provider"
            onChange={(event) => setLlmProvider(event.target.value as LlmProvider)}
            value={llmProvider}
          >
            <option value="mock">{formatEnumLabel(t, "llm_provider", "mock")}</option>
            <option value="openai_compatible">
              {formatEnumLabel(t, "llm_provider", "openai_compatible")}
            </option>
          </select>
        </label>
        {product === "worldline" ? (
          <label className="form-field">
            <span>{t("worldline.modeSelect")}</span>
            <select
              name="worldline_provider"
              onChange={(event) =>
                setWorldlineProvider(event.target.value as WorldlineProvider)
              }
              value={worldlineProvider}
            >
              <option value="deterministic_mock">{t("worldline.deterministicMock")}</option>
              <option value="llm">{t("worldline.llmChunk")}</option>
            </select>
            <span className="muted">{t("worldline.llmChunkHelp")}</span>
          </label>
        ) : null}
        <label className="checkbox-card">
          <input
            checked={realLlmEnabled}
            name="llm_real_enabled"
            onChange={(event) => setRealLlmEnabled(event.target.checked)}
            type="checkbox"
          />
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
        <section className="generation-plan full">
          <div>
            <h3>{t("scenarioCreate.callPlanTitle")}</h3>
            <p className="muted">{t("scenarioCreate.callPlanHelp")}</p>
          </div>
          <div className="generation-plan-grid">
            <div>
              <span>{t("scenarioCreate.callPlanReport")}</span>
              <strong>{reportNarrativeLabel}</strong>
            </div>
            <div>
              <span>{t("scenarioCreate.callPlanWorldline")}</span>
              <strong>{worldlinePlaybackLabel}</strong>
            </div>
            <div>
              <span>{t("scenarioCreate.callPlanNetwork")}</span>
              <strong>{realCallLabel}</strong>
            </div>
            <div>
              <span>{t("scenarioCreate.callPlanDays")}</span>
              <strong>{plannedDayCount}</strong>
            </div>
            <div>
              <span>{t("scenarioCreate.callPlanChunks")}</span>
              <strong>{estimatedChunkCount}</strong>
            </div>
          </div>
          <p className="muted">{t("scenarioCreate.callPlanEstimateHelp")}</p>
        </section>
      </div>
      </section>

      <details className="advanced-settings-panel scenario-advanced-settings">
        <summary>
          <span className="form-section-index" aria-hidden="true">02</span>
          <span>
            <strong>{t("scenarioCreate.advancedSettings")}</strong>
            <small>{t("scenarioCreate.advancedSettingsHelp")}</small>
          </span>
        </summary>
        <div className="form-grid">
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
          <select
            name="llm_chunk_size_days"
            onChange={(event) =>
              setChunkSizeDays(normalizePresetChunkSize(Number(event.target.value)))
            }
            value={String(chunkSizeDays)}
          >
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
            defaultValue={String(DEFAULT_LLM_MAX_OUTPUT_TOKENS)}
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
                name="llm_preset_id"
                onChange={(event) => setSelectedPresetId(event.target.value)}
                value={selectedPresetId}
              >
                <option value="">{t("scenarioCreate.llmPresetSelect")}</option>
                {llmPresets.map((preset) => (
                  <option key={preset.preset_id} value={preset.preset_id}>
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
              disabled={generationInProgress}
              onClick={testCurrentLlmConnection}
              type="button"
            >
              {t("worldline.regenerateTestConnection")}
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
          {presetMessage ? (
            <p aria-live="polite" className="muted" role="status">
              {presetMessage}
            </p>
          ) : null}
          <LlmConnectionTestResult feedback={connectionFeedback} />
        </section>
        <div className="notice full">
          <p>{t("scenarioCreate.llmApiKeyNote")}</p>
          <p>{t("scenarioCreate.realLlmEnablementNote")}</p>
        </div>
      </div>
      </details>
      <section className="stack scenario-agent-settings">
        <div className="form-section-heading">
          <span className="form-section-index" aria-hidden="true">03</span>
          <h2>{t("scenarioCreate.agentGroups")}</h2>
        </div>
        <AgentSelector agents={agents} />
      </section>
      <div className="scenario-launch-zone">
      <button
        className="scenario-launch-button"
        disabled={!dateRangeValid || (progress.active && progress.phase !== "error")}
        type="submit"
      >
        {progress.active && progress.phase !== "error"
          ? t("scenarioCreate.generating")
          : product === "worldline"
            ? t("worldline.generate")
            : t("scenarioCreate.generate")}
      </button>
      <p className="muted scenario-launch-note">{t("worldline.launchNote")}</p>
      </div>
      {progress.active ? (
        <section className={`notice scenario-progress ${progress.phase}`}>
          <div className="scenario-progress-header">
            <strong>{t("scenarioCreate.progressTitle")}</strong>
            <span>{progressPct}%</span>
          </div>
          <div
            aria-label={t("scenarioCreate.progressTitle")}
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={progressPct}
            className="scenario-progress-bar"
            role="progressbar"
          >
            <div style={{ width: `${progressPct}%` }} />
          </div>
          <p aria-atomic="true" aria-live="polite" role="status">
            {progress.message}
          </p>
          {generationInProgress ? (
            <p className="muted">{t("common.keepTabOpen")}</p>
          ) : null}
          {progress.phase === "error" && progress.savedReportPath ? (
            <div className="stack">
              <p className="muted">{t("scenarioCreate.progressPartialSaved")}</p>
              <div className="button-row">
                <Link className="button secondary" href={progress.savedReportPath}>
                  {product === "worldline"
                    ? t("scenarioCreate.openSavedWorldline")
                    : t("scenarioCreate.openSavedScenario")}
                </Link>
              </div>
            </div>
          ) : null}
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
    llm_preset_id: optionalString(getString(formData, "llm_preset_id")),
    llm_real_enabled: formData.get("llm_real_enabled") === "on",
    llm_base_url: optionalString(getString(formData, "llm_base_url")),
    llm_model: optionalString(getString(formData, "llm_model")),
    llm_api_key: optionalString(getString(formData, "llm_api_key")),
    llm_user_prompt: optionalString(getString(formData, "llm_user_prompt")),
    llm_timeout_seconds: optionalNumber(getString(formData, "llm_timeout_seconds")),
    llm_max_output_tokens: optionalNumber(getString(formData, "llm_max_output_tokens")),
    llm_call_delay_seconds: optionalNumber(getString(formData, "llm_call_delay_seconds")),
    visibility: (getString(formData, "visibility") || "private") as Visibility,
    mode: "daily_association_only",
    language: (getString(formData, "language") || "en") as ReportLanguage,
    worldline_provider: (
      getString(formData, "worldline_provider") || "deterministic_mock"
    ) as WorldlineProvider,
    worldline_chunk_days: clampNumber(
      optionalNumber(getString(formData, "llm_chunk_size_days")) ??
        DEFAULT_LLM_CHUNK_SIZE_DAYS,
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

async function waitForNextChunk({
  completedChunks,
  delaySeconds,
  nextChunk,
  setProgress,
  totalChunks,
  waitingLabel,
  nextChunkLabel,
}: {
  completedChunks: number;
  delaySeconds: number;
  nextChunk: { start: string; end: string };
  setProgress: (progress: GenerationProgress) => void;
  totalChunks: number;
  waitingLabel: string;
  nextChunkLabel: string;
}) {
  let remainingMilliseconds = Math.max(0, Math.round(delaySeconds * 1000));
  while (remainingMilliseconds > 0) {
    const displayedSeconds = Math.max(1, Math.ceil(remainingMilliseconds / 1000));
    setProgress({
      active: true,
      phase: "delay",
      currentChunk: completedChunks,
      totalChunks,
      message: `${waitingLabel}: ${displayedSeconds}s · ${nextChunkLabel} ${
        completedChunks + 1
      }/${totalChunks}: ${nextChunk.start} → ${nextChunk.end}`,
    });
    const interval = Math.min(1000, remainingMilliseconds);
    await sleep(interval);
    remainingMilliseconds -= interval;
  }
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

function inclusiveDateCount(startDate: string, endDate: string): number {
  const start = parseDate(startDate);
  const end = parseDate(endDate);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    return 0;
  }
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
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

function worldlineChunkPerformedNetworkCall(
  report: ScenarioReport,
  chunkIndex: number,
): boolean {
  const provenance = report.worldline_simulation?.provenance;
  const history = Array.isArray(provenance?.chunk_history)
    ? provenance.chunk_history
    : [];
  const currentChunk = history.find(
    (item): item is Record<string, unknown> =>
      typeof item === "object"
      && item !== null
      && !Array.isArray(item)
      && Number(item.chunk_index) === chunkIndex,
  );
  return currentChunk
    ? currentChunk.network_call_performed === true
    : provenance?.network_call_performed === true;
}

function getDefaultScenarioTitle(language: string): string {
  return language === "zh-Hant" ? "未來 30 日市場世界線推演" : "30-Day Market Worldline";
}

function getDefaultScenarioDescription(language: string): string {
  return language === "zh-Hant"
    ? "使用日線研究脈絡、代理群體與安全邊界，生成本地世界線推演。"
    : "Local worldline rehearsal using daily research context, agent groups, and safety boundaries.";
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

function readLlmPresetFromForm(
  form: HTMLFormElement,
  name: string,
  includeApiKey: boolean,
): LlmPresetSaveRequest {
  const formData = new FormData(form);
  return {
    name,
    provider: (getString(formData, "llm_provider") || DEFAULT_LLM_PROVIDER) as LlmProvider,
    real_enabled: formData.get("llm_real_enabled") === "on",
    base_url: optionalString(getString(formData, "llm_base_url")),
    model: getString(formData, "llm_model"),
    chunk_size_days: normalizePresetChunkSize(
      Number(
        getString(formData, "llm_chunk_size_days") || DEFAULT_LLM_CHUNK_SIZE_DAYS,
      ),
    ),
    call_delay_seconds: Number(getString(formData, "llm_call_delay_seconds") || DEFAULT_LLM_CALL_DELAY_SECONDS),
    timeout_seconds: Number(getString(formData, "llm_timeout_seconds") || "120"),
    max_output_tokens: Number(
      getString(formData, "llm_max_output_tokens") || DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    ),
    custom_user_prompt: optionalString(getString(formData, "llm_user_prompt")),
    worldline_provider: getString(formData, "worldline_provider") || "deterministic_mock",
    api_key: includeApiKey ? optionalString(getString(formData, "llm_api_key")) : null,
    keep_existing_api_key: true,
    default_language: getString(formData, "language") || "en",
  };
}

function applyLlmPresetToForm(form: HTMLFormElement, preset: LlmPresetSummary) {
  setFormValue(form, "llm_provider", preset.provider);
  setFormChecked(form, "llm_real_enabled", preset.real_enabled);
  setFormValue(form, "llm_base_url", preset.base_url || "");
  setFormValue(form, "llm_model", preset.model || "");
  setFormValue(
    form,
    "llm_chunk_size_days",
    String(normalizePresetChunkSize(preset.chunk_size_days)),
  );
  setFormValue(
    form,
    "llm_call_delay_seconds",
    String(preset.call_delay_seconds ?? DEFAULT_LLM_CALL_DELAY_SECONDS),
  );
  setFormValue(form, "llm_timeout_seconds", String(preset.timeout_seconds));
  setFormValue(form, "llm_max_output_tokens", String(preset.max_output_tokens));
  setFormValue(form, "llm_user_prompt", preset.custom_user_prompt || "");
  setFormValue(form, "worldline_provider", preset.worldline_provider || "deterministic_mock");
  setFormValue(form, "llm_api_key", "");
}

function normalizePresetChunkSize(value: number): 1 | 2 | 3 | 5 {
  return value === 1 || value === 2 || value === 3 || value === 5
    ? value
    : DEFAULT_LLM_CHUNK_SIZE_DAYS;
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

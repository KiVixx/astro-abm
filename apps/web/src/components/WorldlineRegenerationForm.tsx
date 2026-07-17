"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  createLlmPreset,
  deleteLlmPreset,
  regenerateScenarioWorldlineFromChunk,
  testLlmPreset,
  updateLlmPreset,
} from "@/lib/api";
import type {
  LlmPresetSaveRequest,
  LlmPresetSummary,
  ScenarioReport,
} from "@/lib/types";
import { useI18n } from "@/i18n/useI18n";
import { useLeaveWarning } from "@/lib/useLeaveWarning";

interface Settings {
  name: string;
  realEnabled: boolean;
  baseUrl: string;
  model: string;
  apiKey: string;
  timeoutSeconds: string;
  maxOutputTokens: string;
  callDelaySeconds: string;
  customUserPrompt: string;
}

interface RegenerationProgress {
  currentChunk: number;
  message: string;
  phase: "idle" | "chunk" | "delay" | "done" | "error";
  totalChunks: number;
}

export function WorldlineRegenerationForm({
  initialDate,
  presets: initialPresets,
  report,
  startChunkIndex,
}: {
  initialDate?: string;
  presets: LlmPresetSummary[];
  report: ScenarioReport;
  startChunkIndex: number;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const config = report.worldline_simulation?.generation_config;
  const [presets, setPresets] = useState(initialPresets);
  const [selectedPresetId, setSelectedPresetId] = useState(config?.preset_id || "");
  const [settings, setSettings] = useState<Settings>(() => ({
    name: config?.preset_name || "Worldline LLM",
    realEnabled: config?.llm_real_enabled ?? true,
    baseUrl: config?.llm_base_url || "",
    model: config?.llm_model || "",
    apiKey: "",
    timeoutSeconds: String(config?.llm_timeout_seconds || 120),
    maxOutputTokens: String(config?.llm_max_output_tokens || 32000),
    callDelaySeconds: String(config?.llm_call_delay_seconds || 6),
    customUserPrompt: config?.custom_user_prompt || "",
  }));
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const chunkSize = normalizeChunkSize(config?.worldline_chunk_days);
  const chunks = useMemo(
    () => buildChunks((report.daily_timeline || []).map((item) => item.date), chunkSize),
    [chunkSize, report.daily_timeline],
  );
  const selectedChunk = chunks[startChunkIndex];
  const affectedChunks = Math.max(0, chunks.length - startChunkIndex);
  const [progress, setProgress] = useState<RegenerationProgress>({
    currentChunk: 0,
    message: "",
    phase: "idle",
    totalChunks: affectedChunks,
  });
  const selectedPreset = presets.find((preset) => preset.preset_id === selectedPresetId);
  const lastRegeneration = report.worldline_simulation?.last_regeneration;
  const resumableRegenerationId =
    report.worldline_simulation?.continuity_status === "rebuilding" &&
    lastRegeneration &&
    typeof lastRegeneration.regeneration_id === "string" &&
    Number(lastRegeneration.next_chunk_index) === startChunkIndex
      ? lastRegeneration.regeneration_id
      : null;
  const progressPct = progress.totalChunks > 0
    ? Math.round((progress.currentChunk / progress.totalChunks) * 100)
    : 0;
  useLeaveWarning(active);

  function recallPreset(presetId: string) {
    setSelectedPresetId(presetId);
    const preset = presets.find((item) => item.preset_id === presetId);
    if (!preset) return;
    setSettings({
      name: preset.name,
      realEnabled: preset.real_enabled,
      baseUrl: preset.base_url || "",
      model: preset.model || "",
      apiKey: "",
      timeoutSeconds: String(preset.timeout_seconds),
      maxOutputTokens: String(preset.max_output_tokens),
      callDelaySeconds: String(preset.call_delay_seconds),
      customUserPrompt: preset.custom_user_prompt || "",
    });
    setMessage(
      preset.has_api_key
        ? t("worldline.regeneratePresetKeyStored")
        : t("worldline.regeneratePresetNoKey"),
    );
  }

  async function savePreset(updateExisting: boolean) {
    setError("");
    try {
      const payload = presetPayload(settings, report.language || "en", chunkSize);
      const saved = updateExisting && selectedPresetId
        ? await updateLlmPreset(selectedPresetId, payload)
        : await createLlmPreset(payload);
      setPresets((current) => [saved, ...current.filter((item) => item.preset_id !== saved.preset_id)]);
      setSelectedPresetId(saved.preset_id);
      setMessage(t("worldline.regeneratePresetSaved"));
      setSettings((current) => ({ ...current, apiKey: "" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("common.unknownError"));
    }
  }

  async function removePreset() {
    if (!selectedPresetId || !window.confirm(t("worldline.regeneratePresetDeleteConfirm"))) return;
    try {
      await deleteLlmPreset(selectedPresetId);
      setPresets((current) => current.filter((item) => item.preset_id !== selectedPresetId));
      setSelectedPresetId("");
      setMessage(t("worldline.regeneratePresetDeleted"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("common.unknownError"));
    }
  }

  async function testPreset() {
    if (!selectedPresetId) return;
    setMessage(t("worldline.regeneratePresetTesting"));
    try {
      const result = await testLlmPreset(selectedPresetId);
      setMessage(`${result.status}: ${result.message}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("common.unknownError"));
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selectedChunk) {
      setError(t("worldline.chunkInfoUnavailable"));
      return;
    }
    if (!window.confirm(t(
      resumableRegenerationId
        ? "worldline.resumeInterruptedConfirm"
        : "worldline.regenerateSettingsConfirm",
    ))) return;
    setActive(true);
    setError("");
    setMessage(t("worldline.regenerationInProgress"));
    try {
      const regenerationId =
        resumableRegenerationId || `regen_${crypto.randomUUID().replaceAll("-", "_")}`;
      const callDelaySeconds = Number(settings.callDelaySeconds) || 0;
      let finalStatus = "completed";
      for (let chunkIndex = startChunkIndex; chunkIndex < chunks.length; chunkIndex += 1) {
        const current = chunkIndex - startChunkIndex + 1;
        const chunk = chunks[chunkIndex];
        setProgress({
          currentChunk: current - 1,
          message: `${t("worldline.regenerateProgressChunk")} ${current}/${affectedChunks}: ${chunk.start} → ${chunk.end}`,
          phase: "chunk",
          totalChunks: affectedChunks,
        });
        const response = await regenerateScenarioWorldlineFromChunk(report.scenario_id, {
          start_chunk_index: chunkIndex,
          regeneration_id: regenerationId,
          progressive: true,
          preset_id: selectedPresetId || null,
          llm_overrides: {
            real_enabled: settings.realEnabled,
            base_url: settings.baseUrl || null,
            model: settings.model || null,
            api_key: settings.apiKey || null,
            timeout_seconds: Number(settings.timeoutSeconds),
            max_output_tokens: Number(settings.maxOutputTokens),
            call_delay_seconds: callDelaySeconds,
            custom_user_prompt: settings.customUserPrompt || null,
          },
        });
        finalStatus = response.regeneration_status;
        setProgress({
          currentChunk: current,
          message: `${t("worldline.regenerateProgressChunk")} ${current}/${affectedChunks}: ${chunk.start} → ${chunk.end}`,
          phase: "chunk",
          totalChunks: affectedChunks,
        });
        const halted = Boolean(
          response.report.worldline_simulation?.last_regeneration?.generation_halted,
        );
        const networkCallPerformed = Boolean(
          response.report.worldline_simulation?.provenance?.network_call_performed,
        );
        if (halted) {
          setActive(false);
          setMessage("");
          setProgress({
            currentChunk: current,
            message: t("worldline.regenerateProgressHalted"),
            phase: "error",
            totalChunks: affectedChunks,
          });
          return;
        }
        if (
          chunkIndex < chunks.length - 1
          && callDelaySeconds > 0
          && networkCallPerformed
        ) {
          setProgress({
            currentChunk: current,
            message: `${t("worldline.regenerateProgressDelay")} ${callDelaySeconds}s`,
            phase: "delay",
            totalChunks: affectedChunks,
          });
          await sleep(callDelaySeconds * 1000);
        }
      }
      if (finalStatus === "failed_fallback") {
        setActive(false);
        setMessage("");
        setProgress({
          currentChunk: affectedChunks,
          message: t("worldline.regenerateProgressFallback"),
          phase: "error",
          totalChunks: affectedChunks,
        });
        return;
      }
      setProgress({
        currentChunk: affectedChunks,
        message: finalStatus === "partial_fallback"
          ? t("worldline.regenerationPartialFallback")
          : finalStatus === "configuration_fallback"
            ? t("worldline.regenerateProgressConfigurationFallback")
            : t("worldline.regenerateProgressDone"),
        phase: "done",
        totalChunks: affectedChunks,
      });
      router.push(
        `/worldlines/${report.scenario_id}${initialDate ? `?date=${encodeURIComponent(initialDate)}` : ""}`,
      );
      router.refresh();
    } catch (caught) {
      setActive(false);
      setMessage("");
      setError(caught instanceof Error ? caught.message : t("common.unknownError"));
      setProgress((current) => ({
        ...current,
        message: caught instanceof Error ? caught.message : t("common.unknownError"),
        phase: "error",
      }));
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <section className="form-section">
        <div>
          <h2>{t("worldline.regenerateLockedContext")}</h2>
          <p className="muted">{t("worldline.regenerateLockedContextHelp")}</p>
        </div>
        <div className="generation-plan-grid">
          <div><span>{t("common.dateRange")}</span><strong>{report.start_date} → {report.end_date}</strong></div>
          <div><span>{t("scenarioCreate.marketSeries")}</span><strong>{report.assets.join(", ")}</strong></div>
          <div><span>{t("scenarioCreate.agentGroups")}</span><strong>{report.agents.length}</strong></div>
          <div><span>{t("worldline.chunkIndex")}</span><strong>#{startChunkIndex + 1} · {selectedChunk?.start} → {selectedChunk?.end}</strong></div>
          <div><span>{t("worldline.regenerateAffectedChunks")}</span><strong>{affectedChunks}</strong></div>
          <div><span>{t("report.generatedLanguage")}</span><strong>{report.language || "legacy"}</strong></div>
        </div>
      </section>

      <section className="form-section">
        <div>
          <h2>{t("worldline.regenerateLlmSettings")}</h2>
          <p className="muted">{t("worldline.regenerateLlmSettingsHelp")}</p>
        </div>
        <div className="form-grid">
          <label className="form-field full">
            <span>{t("scenarioCreate.llmPresetRecall")}</span>
            <select value={selectedPresetId} onChange={(event) => recallPreset(event.target.value)}>
              <option value="">{t("scenarioCreate.llmPresetSelect")}</option>
              {presets.map((preset) => <option value={preset.preset_id} key={preset.preset_id}>{preset.name}</option>)}
            </select>
          </label>
          <label className="form-field"><span>{t("scenarioCreate.llmPresetName")}</span><input value={settings.name} onChange={(event) => setSettings({ ...settings, name: event.target.value })} /></label>
          <label className="form-field"><span>{t("scenarioCreate.llmModel")}</span><input required value={settings.model} onChange={(event) => setSettings({ ...settings, model: event.target.value })} /></label>
          <label className="form-field full"><span>{t("scenarioCreate.llmBaseUrl")}</span><input required value={settings.baseUrl} onChange={(event) => setSettings({ ...settings, baseUrl: event.target.value })} /></label>
          <label className="form-field"><span>{t("scenarioCreate.llmApiKey")}</span><input autoComplete="off" placeholder={selectedPreset?.has_api_key ? t("worldline.regeneratePresetKeyStored") : t("scenarioCreate.llmApiKeyPlaceholder")} type="password" value={settings.apiKey} onChange={(event) => setSettings({ ...settings, apiKey: event.target.value })} /></label>
          <label className="checkbox-card"><input checked={settings.realEnabled} type="checkbox" onChange={(event) => setSettings({ ...settings, realEnabled: event.target.checked })} /><span>{t("scenarioCreate.llmRealEnabled")}</span></label>
          <label className="form-field"><span>{t("scenarioCreate.llmTimeoutSeconds")}</span><input min="1" max="600" type="number" value={settings.timeoutSeconds} onChange={(event) => setSettings({ ...settings, timeoutSeconds: event.target.value })} /></label>
          <label className="form-field"><span>{t("scenarioCreate.llmMaxOutputTokens")}</span><input min="512" max="32000" type="number" value={settings.maxOutputTokens} onChange={(event) => setSettings({ ...settings, maxOutputTokens: event.target.value })} /></label>
          <label className="form-field"><span>{t("scenarioCreate.llmCallDelaySeconds")}</span><input min="0" max="120" step="0.5" type="number" value={settings.callDelaySeconds} onChange={(event) => setSettings({ ...settings, callDelaySeconds: event.target.value })} /></label>
          <label className="form-field full"><span>{t("scenarioCreate.llmUserPrompt")}</span><textarea rows={5} value={settings.customUserPrompt} onChange={(event) => setSettings({ ...settings, customUserPrompt: event.target.value })} /></label>
        </div>
        <div className="button-row">
          <button className="button secondary" type="button" onClick={() => savePreset(false)}>{t("worldline.regenerateSaveNewPreset")}</button>
          <button className="button secondary" disabled={!selectedPresetId} type="button" onClick={() => savePreset(true)}>{t("worldline.regenerateUpdatePreset")}</button>
          <button className="button secondary" disabled={!selectedPresetId} type="button" onClick={testPreset}>{t("worldline.regenerateTestPreset")}</button>
          <button className="button secondary" disabled={!selectedPresetId} type="button" onClick={removePreset}>{t("scenarioCreate.llmPresetDelete")}</button>
        </div>
      </section>

      <section className="notice warning"><strong>{t("worldline.regenerateDownstreamWarning")}</strong><p>{t("worldline.regenerateLocalSecretNote")}</p></section>
      {resumableRegenerationId ? (
        <p className="notice">{t("worldline.resumeUsesSavedRun")}</p>
      ) : null}
      {settings.realEnabled && !selectedPreset?.has_api_key && !settings.apiKey ? (
        <p className="notice warning">{t("worldline.regenerateCredentialWarning")}</p>
      ) : null}
      {message ? <p className="notice">{message}</p> : null}
      {error ? <p className="notice warning">{error}</p> : null}
      <button disabled={active || !selectedChunk} type="submit">
        {active
          ? t("worldline.regenerationInProgress")
          : resumableRegenerationId
            ? t("worldline.resumeInterruptedRegeneration")
            : t("worldline.regenerateFromHere")}
      </button>
      {progress.phase !== "idle" ? (
        <section className={`notice scenario-progress ${progress.phase}`}>
          <div className="scenario-progress-header">
            <strong>{t("worldline.regenerateProgressTitle")}</strong>
            <span>{progressPct}%</span>
          </div>
          <div className="scenario-progress-bar" aria-hidden="true">
            <div style={{ width: `${progressPct}%` }} />
          </div>
          <p>{progress.message}</p>
          {active ? <p className="muted">{t("common.keepTabOpen")}</p> : null}
        </section>
      ) : null}
    </form>
  );
}

function presetPayload(
  settings: Settings,
  language: string,
  chunkSize: 1 | 2 | 3 | 5,
): LlmPresetSaveRequest {
  return {
    name: settings.name.trim() || "Worldline LLM",
    provider: "openai_compatible",
    real_enabled: settings.realEnabled,
    base_url: settings.baseUrl || null,
    model: settings.model || null,
    api_key: settings.apiKey || null,
    keep_existing_api_key: true,
    worldline_provider: "llm",
    chunk_size_days: chunkSize,
    call_delay_seconds: Number(settings.callDelaySeconds),
    timeout_seconds: Number(settings.timeoutSeconds),
    max_output_tokens: Number(settings.maxOutputTokens),
    custom_user_prompt: settings.customUserPrompt || null,
    default_language: language,
  };
}

function normalizeChunkSize(value: unknown): 1 | 2 | 3 | 5 {
  return value === 1 || value === 2 || value === 3 || value === 5 ? value : 3;
}

function buildChunks(dates: string[], chunkSize: number) {
  const chunks: Array<{ start: string; end: string }> = [];
  for (let index = 0; index < dates.length; index += chunkSize) {
    const values = dates.slice(index, index + chunkSize);
    if (values.length) chunks.push({ start: values[0], end: values[values.length - 1] });
  }
  return chunks;
}

function sleep(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

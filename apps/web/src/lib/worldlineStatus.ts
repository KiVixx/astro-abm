import type { WorldlineSimulation } from "@/lib/types";

const CONFIGURATION_FALLBACK_REASONS = new Set([
  "unsupported_llm_provider",
  "real_llm_disabled",
  "llm_base_url_missing",
  "llm_model_missing",
  "legacy_configuration_unavailable",
]);

const LEGACY_CONFIGURATION_OUTPUT_STATUSES = new Set([
  "configuration_missing",
  "llm_disabled_or_config_unavailable",
  "not_run",
]);

export interface WorldlineFallbackBreakdown {
  configurationFallback: number;
  llmFailed: number;
  skipped: number;
  reasonCounts: Record<string, number>;
}

export function worldlineFallbackBreakdown(
  simulation: WorldlineSimulation,
): WorldlineFallbackBreakdown {
  const provenance = simulation.provenance || {};
  const history = Array.isArray(provenance.chunk_history)
    ? provenance.chunk_history.filter(isRecord)
    : [];
  const reasonCounts = isRecord(provenance.fallback_reason_counts)
    ? Object.fromEntries(
        Object.entries(provenance.fallback_reason_counts)
          .map(([reason, count]) => [reason, numberFromUnknown(count)] as const)
          .filter(([, count]) => count > 0),
      )
    : history.reduce<Record<string, number>>((counts, chunk) => {
        const reason = fallbackReason(chunk);
        if (reason) counts[reason] = (counts[reason] || 0) + 1;
        return counts;
      }, {});
  const inferredConfigurationFallback = Object.entries(reasonCounts)
    .filter(([reason]) => CONFIGURATION_FALLBACK_REASONS.has(reason))
    .reduce((total, [, count]) => total + count, 0);
  const inferredLlmFailed = history.filter(
    (chunk) => chunk.status === "fallback"
      && !CONFIGURATION_FALLBACK_REASONS.has(fallbackReason(chunk)),
  ).length;
  return {
    configurationFallback: numberOrFallback(
      provenance.configuration_fallback_chunk_count,
      inferredConfigurationFallback,
    ),
    llmFailed: numberOrFallback(provenance.llm_failed_chunk_count, inferredLlmFailed),
    skipped: history.filter((chunk) => chunk.status === "skipped_after_halt").length,
    reasonCounts,
  };
}

export function worldlineDisplayStatus(simulation: WorldlineSimulation): string {
  if (simulation.provenance?.generation_halted === true) return "halted";
  const lastRegeneration = simulation.last_regeneration;
  if (!lastRegeneration) return simulation.status;
  const stored = String(lastRegeneration.status || "");
  if (stored) return stored;

  const regeneratedAt = String(lastRegeneration.regenerated_at || "");
  const history = Array.isArray(simulation.provenance?.chunk_history)
    ? simulation.provenance.chunk_history
    : [];
  const regeneratedChunks = history.filter(
    (value): value is Record<string, unknown> =>
      typeof value === "object"
      && value !== null
      && !Array.isArray(value)
      && regeneratedAt !== ""
      && String(value.regenerated_at || "") === regeneratedAt,
  );
  if (!regeneratedChunks.length) return simulation.status;

  const completed = regeneratedChunks.filter((chunk) => chunk.status === "completed").length;
  const failed = regeneratedChunks.filter(
    (chunk) => chunk.status === "fallback" || chunk.status === "skipped_after_halt",
  ).length;
  if (failed === 0) return "completed";
  return completed > 0 ? "partial_fallback" : "failed_fallback";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function numberFromUnknown(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function numberOrFallback(value: unknown, fallback: number): number {
  return value === undefined || value === null ? fallback : numberFromUnknown(value);
}

function fallbackReason(chunk: Record<string, unknown>): string {
  if (typeof chunk.fallback_reason === "string" && chunk.fallback_reason) {
    return chunk.fallback_reason;
  }
  if (
    chunk.status === "fallback"
    && chunk.network_call_performed !== true
    && LEGACY_CONFIGURATION_OUTPUT_STATUSES.has(String(chunk.output_validation_status || ""))
  ) {
    return "legacy_configuration_unavailable";
  }
  return "";
}

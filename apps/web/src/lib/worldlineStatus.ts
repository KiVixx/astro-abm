import type { WorldlineSimulation } from "@/lib/types";

export function worldlineDisplayStatus(simulation: WorldlineSimulation): string {
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

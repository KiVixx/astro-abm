import type { WorldlineSimulation } from "./types";

export function worldlineGenerationMode(
  simulation: WorldlineSimulation | null | undefined,
): string {
  if (!simulation) {
    return "";
  }
  const provenanceMode = simulation.provenance?.generation_mode;
  return typeof provenanceMode === "string" && provenanceMode
    ? provenanceMode
    : simulation.mode;
}

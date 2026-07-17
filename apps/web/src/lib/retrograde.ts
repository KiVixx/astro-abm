export const RETROGRADE_BODIES = [
  "Mercury",
  "Venus",
  "Mars",
  "Jupiter",
  "Saturn",
  "Uranus",
  "Neptune",
  "Pluto",
] as const;

export type RetrogradeBody = (typeof RETROGRADE_BODIES)[number];

export function isRetrogradeBody(value: string): value is RetrogradeBody {
  return RETROGRADE_BODIES.includes(value as RetrogradeBody);
}

export function parseRetrogradeSelection(value: string | null): RetrogradeBody[] {
  if (value === null) {
    return [...RETROGRADE_BODIES];
  }
  if (value === "none") {
    return [];
  }
  const selected = value
    .split(",")
    .map((body) => body.trim())
    .filter(isRetrogradeBody);
  return RETROGRADE_BODIES.filter((body) => selected.includes(body));
}

export function serializeRetrogradeSelection(bodies: RetrogradeBody[]): string {
  return bodies.length ? bodies.join(",") : "none";
}

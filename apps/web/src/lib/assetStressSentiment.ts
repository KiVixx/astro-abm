import type { DailyScenarioSnapshot, ScenarioReport } from "./types";

export type AssetStressSource =
  | "llm_scenario_metric"
  | "timeline_metric"
  | "mock_demo";

export interface AssetStressPoint {
  asset: string;
  date: string;
  value: number;
  source: AssetStressSource;
  color: string;
}

export interface AssetStressSeries {
  asset: string;
  color: string;
  min: number;
  max: number;
  points: AssetStressPoint[];
}

const ASSET_COLORS = [
  "#176b87",
  "#9b4f35",
  "#28704f",
  "#6b5c93",
  "#b7791f",
  "#5c6670",
  "#0f766e",
  "#8a4f7d",
];

const METRIC_KEYS = [
  "sentiment_stress_support",
  "sentiment_stress",
  "asset_stress_sentiment",
  "stress_sentiment",
  "fear_greed_stress",
];

export function assetStressColor(index: number): string {
  return ASSET_COLORS[index % ASSET_COLORS.length];
}

function clampStressValue(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function numberFrom(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return clampStressValue(value);
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? clampStressValue(parsed) : null;
  }
  return null;
}

function extractMetricFromAssetBucket(
  snapshotRecord: Record<string, unknown>,
  asset: string,
): number | null {
  const candidateBuckets = [
    snapshotRecord.asset_metrics,
    snapshotRecord.asset_sentiment_stress,
    snapshotRecord.asset_stress_sentiment,
    snapshotRecord.metrics,
  ];

  for (const bucket of candidateBuckets) {
    if (!isRecord(bucket)) {
      continue;
    }
    const directValue = numberFrom(bucket[asset]);
    if (directValue !== null) {
      return directValue;
    }
    const assetMetrics = bucket[asset];
    if (!isRecord(assetMetrics)) {
      continue;
    }
    for (const metricKey of METRIC_KEYS) {
      const metricValue = numberFrom(assetMetrics[metricKey]);
      if (metricValue !== null) {
        return metricValue;
      }
    }
  }

  return null;
}

function extractLlmMetric(
  report: ScenarioReport | undefined,
  snapshot: DailyScenarioSnapshot,
  asset: string,
): number | null {
  const indicators = report?.llm_report?.asset_stress_indicators || [];
  const normalizedAsset = asset.toUpperCase();
  const indicator = indicators.find(
    (item) =>
      item.date === snapshot.date &&
      item.asset.toUpperCase() === normalizedAsset &&
      Number.isFinite(item.sentiment_stress_support),
  );
  return indicator ? clampStressValue(indicator.sentiment_stress_support) : null;
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 9973;
  }
  return hash;
}

function regimeBase(snapshot: DailyScenarioSnapshot): number {
  const stressRegime = snapshot.market_context.stress_regime;
  const volatilityRegime = snapshot.market_context.volatility_regime;
  const stressBase =
    stressRegime === "stress"
      ? 78
      : stressRegime === "elevated"
        ? 66
        : stressRegime === "watchful"
          ? 50
          : 34;
  const volatilityAdjustment =
    volatilityRegime === "expanded"
      ? 10
      : volatilityRegime === "compressed"
        ? -7
        : 0;
  return stressBase + volatilityAdjustment;
}

function mockStressValue(
  snapshot: DailyScenarioSnapshot,
  asset: string,
  assetIndex: number,
): number {
  const hash = hashString(`${asset}:${snapshot.date}`);
  const wave = Math.sin((snapshot.day_index + assetIndex * 3) / 4) * 9;
  const texture = (hash % 17) - 8;
  return clampStressValue(Math.round((regimeBase(snapshot) + wave + texture) * 10) / 10);
}

export function assetStressPointForSnapshot(
  snapshot: DailyScenarioSnapshot,
  asset: string,
  assetIndex = 0,
  report?: ScenarioReport,
): AssetStressPoint {
  const llmMetric = extractLlmMetric(report, snapshot, asset);
  if (llmMetric !== null) {
    return {
      asset,
      date: snapshot.date,
      value: llmMetric,
      source: "llm_scenario_metric",
      color: assetStressColor(assetIndex),
    };
  }

  const snapshotRecord = snapshot as unknown as Record<string, unknown>;
  const extracted = extractMetricFromAssetBucket(snapshotRecord, asset);
  const value = extracted ?? mockStressValue(snapshot, asset, assetIndex);
  return {
    asset,
    date: snapshot.date,
    value,
    source: extracted === null ? "mock_demo" : "timeline_metric",
    color: assetStressColor(assetIndex),
  };
}

export function buildAssetStressSeries(
  report: ScenarioReport,
  timeline: DailyScenarioSnapshot[],
): AssetStressSeries[] {
  const assets = Array.from(
    new Set([
      ...report.assets,
      ...timeline.flatMap((snapshot) => snapshot.assets),
    ]),
  ).filter(Boolean);

  return assets.map((asset, assetIndex) => {
    const points = timeline.map((snapshot) =>
      assetStressPointForSnapshot(snapshot, asset, assetIndex, report),
    );
    const values = points.map((point) => point.value);
    return {
      asset,
      color: assetStressColor(assetIndex),
      min: values.length ? Math.min(...values) : 0,
      max: values.length ? Math.max(...values) : 100,
      points,
    };
  });
}

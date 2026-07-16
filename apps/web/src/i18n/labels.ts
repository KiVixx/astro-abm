import type { AgentProfile } from "@/lib/types";
import type { TranslationKey } from "./dictionary";

type LabelMap = Record<string, TranslationKey>;

const enumLabels: Record<string, LabelMap> = {
  visibility: {
    private: "value.visibility.private",
    public: "value.visibility.public",
  },
  llm_provider: {
    mock: "value.llm.mock",
    openai_compatible: "value.llm.openaiCompatible",
  },
  llm_status: {
    not_requested: "value.llmStatus.notRequested",
    completed: "value.llmStatus.completed",
    dry_run: "value.llmStatus.dryRun",
    failed: "value.llmStatus.failed",
    safety_review_failed: "value.llmStatus.safetyReviewFailed",
    invalid_output: "value.llmStatus.invalidOutput",
  },
  scenario_mode: {
    daily_association_only: "value.mode.dailyAssociationOnly",
  },
  report_language: {
    en: "value.reportLanguage.en",
    "zh-Hant": "value.reportLanguage.zhHant",
    legacy: "value.reportLanguage.legacy",
  },
  agent_category: {
    retail: "value.agentCategory.retail",
    trading: "value.agentCategory.trading",
    institutional: "value.agentCategory.institutional",
    company_type: "value.agentCategory.companyType",
  },
  agent_level: {
    low: "value.agentLevel.low",
    low_to_medium: "value.agentLevel.lowToMedium",
    medium: "value.agentLevel.medium",
    high: "value.agentLevel.high",
    very_high: "value.agentLevel.veryHigh",
  },
  time_horizon: {
    intraday_to_days: "value.timeHorizon.intradayToDays",
    hours_to_days: "value.timeHorizon.hoursToDays",
    weeks_to_quarters: "value.timeHorizon.weeksToQuarters",
    months_to_years: "value.timeHorizon.monthsToYears",
    quarters_to_years: "value.timeHorizon.quartersToYears",
  },
  decision_style: {
    "reactive narrative-following": "value.decisionStyle.reactiveNarrative",
    "slow conviction-based review": "value.decisionStyle.slowConviction",
    "fast risk-adjustment": "value.decisionStyle.fastRiskAdjustment",
    "scenario-weighted allocation review": "value.decisionStyle.scenarioWeighted",
    "committee-based strategic planning": "value.decisionStyle.committeeStrategic",
    "risk committee balance-sheet review": "value.decisionStyle.riskCommittee",
    "operational hedging and capital planning": "value.decisionStyle.operationalHedging",
  },
  stress_regime: {
    stress: "value.stress.stress",
    elevated: "value.stress.elevated",
    watchful: "value.stress.watchful",
    calm: "value.stress.calm",
    normal: "value.common.normal",
    unknown_future: "value.common.unknownFuture",
    unknown_placeholder: "value.common.unknownPlaceholder",
  },
  volatility_regime: {
    expanded: "value.volatility.expanded",
    compressed: "value.volatility.compressed",
    normal: "value.common.normal",
    unknown_future: "value.common.unknownFuture",
  },
  liquidity_regime: {
    selective: "value.liquidity.selective",
    orderly: "value.liquidity.orderly",
    thin: "value.liquidity.thin",
    normal: "value.common.normal",
    unknown_future: "value.common.unknownFuture",
  },
  data_quality: {
    local_research_available: "value.dataQuality.localResearchAvailable",
    low_research_context_confidence: "value.dataQuality.lowResearchContextConfidence",
    low_association_confidence: "value.dataQuality.lowAssociationConfidence",
    low_placeholder_confidence: "value.dataQuality.lowPlaceholderConfidence",
    computed_ephemeris_available: "value.dataQuality.computedEphemerisAvailable",
    placeholder_fallback: "value.dataQuality.placeholderFallback",
    future_placeholder: "value.dataQuality.futurePlaceholder",
    legacy_report: "value.dataQuality.legacyReport",
    unknown: "value.common.unknown",
  },
  data_source: {
    local_research_snapshot: "value.dataSource.localResearchSnapshot",
    computed_ephemeris: "value.dataSource.computedEphemeris",
    mixed_computed_research: "value.dataSource.mixedComputedResearch",
    placeholder_fallback: "value.dataSource.placeholderFallback",
    future_placeholder: "value.dataSource.futurePlaceholder",
    legacy_report: "value.dataSource.legacyReport",
  },
  coverage_status: {
    available: "value.coverage.available",
    missing: "value.coverage.missing",
    future_placeholder: "value.dataQuality.futurePlaceholder",
    mixed: "value.coverage.mixed",
    unknown: "value.common.unknown",
  },
  date_range_mode: {
    future: "value.dateRange.future",
    historical: "value.dateRange.historical",
    mixed: "value.dateRange.mixed",
    empty: "value.dateRange.empty",
  },
  series_type: {
    crypto_price: "value.seriesType.cryptoPrice",
    equity_index: "value.seriesType.equityIndex",
    commodity_price: "value.seriesType.commodityPrice",
    currency_index: "value.seriesType.currencyIndex",
    volatility_index: "value.seriesType.volatilityIndex",
    rate_series: "value.seriesType.rateSeries",
    custom: "value.seriesType.custom",
  },
  astro_intensity: {
    high: "value.intensity.high",
    medium: "value.intensity.medium",
    low: "value.intensity.low",
    calm: "value.stress.calm",
  },
};

export const agentNameLabels: Record<string, TranslationKey> = {
  crypto_retail_fomo: "agent.cryptoRetailFomo",
  long_term_holder: "agent.longTermHolder",
  leveraged_trader: "agent.leveragedTrader",
  macro_allocator: "agent.macroAllocator",
  big_tech_company_type: "agent.bigTechCompanyType",
  global_bank_type: "agent.globalBankType",
  energy_company_type: "agent.energyCompanyType",
};

const agentDescriptionLabels: Record<string, TranslationKey> = {
  crypto_retail_fomo: "agentDescription.cryptoRetailFomo",
  long_term_holder: "agentDescription.longTermHolder",
  leveraged_trader: "agentDescription.leveragedTrader",
  macro_allocator: "agentDescription.macroAllocator",
  big_tech_company_type: "agentDescription.bigTechCompanyType",
  global_bank_type: "agentDescription.globalBankType",
  energy_company_type: "agentDescription.energyCompanyType",
};

export function enumLabelKey(group: string, value?: string | null): TranslationKey | null {
  if (!value) {
    return null;
  }
  return enumLabels[group]?.[value] || null;
}

export function formatEnumLabel(
  t: (key: string, fallback?: string) => string,
  group: string,
  value?: string | null,
): string {
  if (!value) {
    return t("value.common.unknown", "Unknown");
  }
  const key = enumLabelKey(group, value);
  return key ? t(key, value) : value.replaceAll("_", " ");
}

export function formatAgentName(
  t: (key: string, fallback?: string) => string,
  agentId: string,
  fallback: string,
): string {
  const key = agentNameLabels[agentId];
  return key ? t(key, fallback) : fallback;
}

export function formatAgentProfileName(
  t: (key: string, fallback?: string) => string,
  agent: Pick<AgentProfile, "agent_id" | "name">,
): string {
  return formatAgentName(t, agent.agent_id, agent.name);
}

export function formatAgentDescription(
  t: (key: string, fallback?: string) => string,
  agentId: string,
  fallback: string,
): string {
  const key = agentDescriptionLabels[agentId];
  return key ? t(key, fallback) : fallback;
}

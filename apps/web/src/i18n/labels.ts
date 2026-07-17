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
  worldline_status: {
    mock_completed: "value.worldlineStatus.mockCompleted",
    completed: "value.worldlineStatus.completed",
    fallback: "value.worldlineStatus.fallback",
    dry_run: "value.worldlineStatus.dryRun",
    failed: "value.worldlineStatus.failed",
    halted: "value.worldlineStatus.halted",
    partial_fallback: "value.worldlineStatus.partialFallback",
    failed_fallback: "value.worldlineStatus.failedFallback",
    configuration_fallback: "value.worldlineStatus.configurationFallback",
    legacy: "value.worldlineStatus.legacy",
    legacy_unknown: "value.worldlineStatus.legacy",
  },
  chunk_status: {
    mock_completed: "value.chunkStatus.mockCompleted",
    completed: "value.chunkStatus.completed",
    fallback: "value.chunkStatus.fallback",
    skipped_after_halt: "value.chunkStatus.skippedAfterHalt",
    dry_run: "value.chunkStatus.dryRun",
    invalid_json: "value.chunkStatus.invalidJson",
    invalid_payload: "value.chunkStatus.invalidPayload",
    request_failed: "value.chunkStatus.requestFailed",
    failed: "value.chunkStatus.failed",
    halted: "value.chunkStatus.halted",
    pending: "value.chunkStatus.pending",
    unknown: "value.common.unknown",
  },
  output_validation_status: {
    valid_json: "value.outputValidation.validJson",
    invalid_json: "value.chunkStatus.invalidJson",
    invalid_payload: "value.chunkStatus.invalidPayload",
    request_failed: "value.chunkStatus.requestFailed",
    configuration_missing: "value.outputValidation.configurationMissing",
    deferred_to_chunk_endpoint: "value.outputValidation.deferred",
    missing_daily_timeline: "value.outputValidation.missingTimeline",
    skipped_after_consecutive_failures: "value.outputValidation.skippedAfterFailures",
    not_run: "value.common.notRun",
    unknown: "value.common.unknown",
  },
  safety_check_status: {
    passed: "value.checkStatus.passed",
    failed: "value.checkStatus.failed",
    not_applied: "value.checkStatus.notApplied",
    not_run: "value.common.notRun",
    unknown: "value.common.unknown",
  },
  continuity_status: {
    consistent: "value.continuityStatus.consistent",
    rebuilding: "value.continuityStatus.rebuilding",
    legacy_unknown: "value.continuityStatus.legacyUnknown",
  },
  generation_source: {
    llm_chunk: "value.generationSource.llmChunk",
    deterministic_mock: "value.generationSource.deterministicMock",
    fallback: "value.generationSource.fallback",
    unknown: "value.common.unknown",
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
  agent_mood: {
    watchful: "value.mood.watchful",
    "narrative-sensitive": "value.mood.narrativeSensitive",
    "exposure-aware": "value.mood.exposureAware",
    "portfolio-aware": "value.mood.portfolioAware",
    "planning-focused": "value.mood.planningFocused",
  },
  edge_type: {
    agent_attention: "value.edgeType.agentAttention",
    context_to_asset: "value.edgeType.contextToAsset",
    context_to_risk: "value.edgeType.contextToRisk",
  },
  sentiment_state: {
    stressed: "value.sentimentState.stressed",
    watchful: "value.mood.watchful",
    calm: "value.stress.calm",
  },
  worldline_regime: {
    stress_liquidity_watch: "value.worldlineRegime.stressLiquidityWatch",
    volatility_expansion_watch: "value.worldlineRegime.volatilityExpansionWatch",
    narrative_pressure_watch: "value.worldlineRegime.narrativePressureWatch",
    balanced_rehearsal_path: "value.worldlineRegime.balancedRehearsalPath",
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

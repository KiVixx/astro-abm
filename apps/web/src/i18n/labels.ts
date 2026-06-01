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
  scenario_mode: {
    daily_association_only: "value.mode.dailyAssociationOnly",
  },
  agent_category: {
    retail: "value.agentCategory.retail",
    trading: "value.agentCategory.trading",
    institutional: "value.agentCategory.institutional",
    company_type: "value.agentCategory.companyType",
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
    placeholder_fallback: "value.dataQuality.placeholderFallback",
    future_placeholder: "value.dataQuality.futurePlaceholder",
    legacy_report: "value.dataQuality.legacyReport",
    unknown: "value.common.unknown",
  },
  data_source: {
    local_research_snapshot: "value.dataSource.localResearchSnapshot",
    placeholder_fallback: "value.dataSource.placeholderFallback",
    future_placeholder: "value.dataSource.futurePlaceholder",
    legacy_report: "value.dataSource.legacyReport",
  },
  coverage_status: {
    available: "value.coverage.available",
    missing: "value.coverage.missing",
    future_placeholder: "value.dataQuality.futurePlaceholder",
    unknown: "value.common.unknown",
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

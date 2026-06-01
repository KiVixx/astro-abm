"use client";

import { useI18n } from "@/i18n/useI18n";

export function SafetyPhrases() {
  const { t } = useI18n();
  return (
    <div className="tag-row" aria-label={t("report.disclaimer")}>
      <span className="tag">{t("safety.associationOnly")}</span>
      <span className="tag">{t("safety.scenarioRehearsalOnly")}</span>
      <span className="tag">{t("safety.notFinancialAdvice")}</span>
      <span className="tag">{t("safety.notTradingSignal")}</span>
    </div>
  );
}


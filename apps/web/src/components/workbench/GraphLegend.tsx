"use client";

import { useI18n } from "@/i18n/useI18n";

const legendItems = [
  ["agent", "legend.agent"],
  ["astro", "legend.astro"],
  ["market", "legend.market"],
  ["asset", "legend.asset"],
  ["risk", "legend.risk"],
  ["data", "legend.data"],
];

export function GraphLegend() {
  const { t } = useI18n();

  return (
    <div className="workbench-legend" aria-label={t("legend.aria")}>
      {legendItems.map(([kind, labelKey]) => (
        <span className="workbench-legend-item" key={kind}>
          <span className={`legend-dot legend-dot-${kind}`} />
          {t(labelKey)}
        </span>
      ))}
      <span className="muted">
        {t("legend.note")}
      </span>
    </div>
  );
}

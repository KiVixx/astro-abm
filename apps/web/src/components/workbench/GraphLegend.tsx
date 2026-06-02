"use client";

import type { AssetStressSeries } from "@/lib/assetStressSentiment";
import { useI18n } from "@/i18n/useI18n";

const legendItems = [
  ["agent", "legend.agent"],
  ["astro", "legend.astro"],
  ["market", "legend.market"],
  ["asset", "legend.asset"],
  ["risk", "legend.risk"],
  ["data", "legend.data"],
];

export function GraphLegend({
  assetStressSeries = [],
}: {
  assetStressSeries?: AssetStressSeries[];
}) {
  const { t } = useI18n();

  return (
    <div className="workbench-legend" aria-label={t("legend.aria")}>
      {legendItems.map(([kind, labelKey]) => (
        <span className="workbench-legend-item" key={kind}>
          <span className={`legend-dot legend-dot-${kind}`} />
          {t(labelKey)}
        </span>
      ))}
      {assetStressSeries.map((series) => (
        <span className="workbench-legend-item" key={`asset-stress-${series.asset}`}>
          <span
            className="legend-line"
            style={{ backgroundColor: series.color }}
          />
          {t("legend.assetStressSentiment")}: {series.asset}
        </span>
      ))}
      <span className="muted">
        {t("legend.note")}
      </span>
    </div>
  );
}

"use client";

import { useI18n } from "@/i18n/useI18n";
import type { WorkbenchNodeType } from "@/lib/workbenchGraph";

const legendItems: Array<{
  kind: string;
  labelKey: string;
  nodeTypes?: WorkbenchNodeType[];
}> = [
  { kind: "agent", labelKey: "legend.agent", nodeTypes: ["agent"] },
  { kind: "astro", labelKey: "legend.astro", nodeTypes: ["astro"] },
  {
    kind: "market",
    labelKey: "legend.market",
    nodeTypes: ["stress", "volatility", "liquidity"],
  },
  { kind: "asset", labelKey: "legend.asset", nodeTypes: ["asset"] },
  { kind: "risk", labelKey: "legend.risk", nodeTypes: ["risk"] },
  { kind: "data", labelKey: "legend.data", nodeTypes: ["data_quality"] },
  { kind: "relationship", labelKey: "legend.relationship" },
  { kind: "asset-stress", labelKey: "legend.assetStressSentiment" },
];

interface GraphLegendProps {
  activeNodeTypes?: Set<WorkbenchNodeType>;
  onToggleNodeTypes?: (nodeTypes: WorkbenchNodeType[]) => void;
}

export function GraphLegend({ activeNodeTypes, onToggleNodeTypes }: GraphLegendProps) {
  const { t } = useI18n();

  return (
    <div className="workbench-legend" aria-label={t("legend.aria")}>
      {legendItems.map(({ kind, labelKey, nodeTypes }) => {
        const isInteractive = Boolean(nodeTypes && activeNodeTypes && onToggleNodeTypes);
        const isActive = nodeTypes?.every((type) => activeNodeTypes?.has(type)) ?? true;
        const content = (
          <>
            <span className={`legend-dot legend-dot-${kind}`} />
            {t(labelKey)}
          </>
        );
        return isInteractive ? (
          <button
            aria-pressed={isActive}
            className={`workbench-legend-item workbench-legend-filter ${isActive ? "is-active" : ""}`}
            key={kind}
            onClick={() => onToggleNodeTypes?.(nodeTypes || [])}
            type="button"
          >
            {content}
          </button>
        ) : (
          <span className="workbench-legend-item" key={kind}>
            {content}
          </span>
        );
      })}
      <span className="muted">
        {onToggleNodeTypes ? t("legend.filterNote") : t("legend.note")}
      </span>
    </div>
  );
}

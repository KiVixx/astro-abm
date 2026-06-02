"use client";

import { GraphLegend } from "./GraphLegend";
import type { AssetStressSeries } from "@/lib/assetStressSentiment";
import type { WorkbenchGraph, WorkbenchNode } from "@/lib/workbenchGraph";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface DailyGraphCanvasProps {
  graph: WorkbenchGraph;
  assetStressSeries: AssetStressSeries[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
}

function shortLabel(value?: string, length = 26): string {
  if (!value) {
    return "";
  }
  return value.length > length ? `${value.slice(0, length - 1)}...` : value;
}

function nodeClassName(node: WorkbenchNode, selectedNodeId: string | null) {
  return [
    "workbench-node",
    `workbench-node-${node.type}`,
    selectedNodeId === node.id ? "is-selected" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function DailyGraphCanvas({
  graph,
  assetStressSeries,
  selectedNodeId,
  onSelectNode,
}: DailyGraphCanvasProps) {
  const { t } = useI18n();
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));

  const displayNodeLabel = (node: WorkbenchNode) => {
    const contextKeys: Partial<Record<WorkbenchNode["type"], string>> = {
      astro: "legend.astro",
      stress: "workbench.contextStress",
      volatility: "workbench.contextVolatility",
      liquidity: "workbench.contextLiquidity",
      data_quality: "legend.data",
    };
    if (node.type === "agent") {
      const agentId = node.id.replace(/^agent_/, "");
      return formatAgentName(t, agentId, node.label);
    }
    const labelKey = contextKeys[node.type];
    return labelKey ? t(labelKey) : node.label;
  };

  const displayNodeSubtitle = (node: WorkbenchNode) => {
    if (!node.subtitle) {
      return "";
    }
    if (node.type === "stress") {
      return formatEnumLabel(t, "stress_regime", node.subtitle);
    }
    if (node.type === "volatility") {
      return formatEnumLabel(t, "volatility_regime", node.subtitle);
    }
    if (node.type === "liquidity") {
      return formatEnumLabel(t, "liquidity_regime", node.subtitle);
    }
    if (node.type === "data_quality") {
      return formatEnumLabel(t, "data_quality", node.subtitle);
    }
    if (node.type === "astro") {
      return formatEnumLabel(t, "astro_intensity", node.subtitle);
    }
    if (node.type === "risk") {
      return t("legend.risk");
    }
    if (node.type === "asset") {
      return t("legend.asset");
    }
    return node.subtitle;
  };

  return (
    <section className="workbench-card workbench-graph-card">
      <div className="workbench-card-header">
        <div>
          <h2>{t("workbench.graphTitle")}</h2>
          <p className="muted">
            {t("workbench.graphHelp")}
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => onSelectNode(null)}
          type="button"
        >
          {t("workbench.clearNode")}
        </button>
      </div>
      <GraphLegend assetStressSeries={assetStressSeries} />
      <div className="workbench-svg-frame">
        <svg
          className="workbench-svg"
          role="img"
          viewBox={`0 0 ${graph.width} ${graph.height}`}
          aria-label={t("workbench.graphAria")}
        >
          <defs>
            <marker
              id="workbench-arrow"
              markerHeight="8"
              markerWidth="8"
              orient="auto"
              refX="8"
              refY="4"
            >
              <path d="M0,0 L8,4 L0,8 z" className="workbench-arrow" />
            </marker>
          </defs>
          <g className="workbench-edges">
            {graph.edges.map((edge) => {
              const source = nodeById.get(edge.source);
              const target = nodeById.get(edge.target);
              if (!source || !target) {
                return null;
              }
              const midOffset = Math.max(80, Math.abs(target.x - source.x) / 2);
              const path = `M ${source.x + 84} ${source.y} C ${
                source.x + midOffset
              } ${source.y}, ${target.x - midOffset} ${target.y}, ${
                target.x - 84
              } ${target.y}`;
              return (
                <path
                  className={`workbench-edge workbench-edge-${edge.type}`}
                  d={path}
                  key={edge.id}
                  markerEnd="url(#workbench-arrow)"
                />
              );
            })}
          </g>
          <g className="workbench-nodes">
            {graph.nodes.map((node) => (
              <g
                className={nodeClassName(node, selectedNodeId)}
                key={node.id}
                onClick={() => onSelectNode(node.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectNode(node.id);
                  }
                }}
                role="button"
                tabIndex={0}
                transform={`translate(${node.x - 82} ${node.y - 34})`}
              >
                <rect height="68" rx="8" width="164" />
                <text className="node-label" x="82" y="28">
                  {shortLabel(displayNodeLabel(node))}
                </text>
                {node.subtitle ? (
                  <text className="node-subtitle" x="82" y="49">
                    {shortLabel(displayNodeSubtitle(node), 24)}
                  </text>
                ) : null}
                <title>{`${displayNodeLabel(node)}${
                  node.subtitle ? ` - ${displayNodeSubtitle(node)}` : ""
                }${node.detail ? `: ${node.detail}` : ""}`}</title>
              </g>
            ))}
          </g>
        </svg>
      </div>
    </section>
  );
}

"use client";

import { GraphLegend } from "./GraphLegend";
import type { WorkbenchGraph, WorkbenchNode } from "@/lib/workbenchGraph";

interface DailyGraphCanvasProps {
  graph: WorkbenchGraph;
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
  selectedNodeId,
  onSelectNode,
}: DailyGraphCanvasProps) {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));

  return (
    <section className="workbench-card workbench-graph-card">
      <div className="workbench-card-header">
        <div>
          <h2>Scenario Graph</h2>
          <p className="muted">
            Agent groups, daily context, assets, and risk themes for the selected
            day.
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => onSelectNode(null)}
          type="button"
        >
          Clear node
        </button>
      </div>
      <GraphLegend />
      <div className="workbench-svg-frame">
        <svg
          className="workbench-svg"
          role="img"
          viewBox={`0 0 ${graph.width} ${graph.height}`}
          aria-label="Scenario workbench graph"
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
                  {shortLabel(node.label)}
                </text>
                {node.subtitle ? (
                  <text className="node-subtitle" x="82" y="49">
                    {shortLabel(node.subtitle, 24)}
                  </text>
                ) : null}
                <title>
                  {node.label}
                  {node.subtitle ? ` - ${node.subtitle}` : ""}
                  {node.detail ? `: ${node.detail}` : ""}
                </title>
              </g>
            ))}
          </g>
        </svg>
      </div>
    </section>
  );
}


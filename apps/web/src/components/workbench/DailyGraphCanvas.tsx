"use client";

import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
} from "d3-force";
import { drag, type D3DragEvent } from "d3-drag";
import { select } from "d3-selection";
import { zoom, zoomIdentity, type D3ZoomEvent, type ZoomBehavior, type ZoomTransform } from "d3-zoom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GraphLegend } from "./GraphLegend";
import type { WorkbenchGraph, WorkbenchNode } from "@/lib/workbenchGraph";
import {
  connectedNodeIds,
  edgeEndpointIds,
  nodeAnchor,
  selectedEdgeNodeIds,
  toForceGraph,
  type ForceGraphEdge,
  type ForceGraphNode,
} from "@/lib/workbenchForceGraph";
import { formatAgentName, formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface DailyGraphCanvasProps {
  graph: WorkbenchGraph;
  selectedDate: string;
  previousDate?: string;
  nextDate?: string;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onSelectDate: (date: string) => void;
  onSelectNode: (nodeId: string | null) => void;
  onSelectEdge: (edgeId: string | null) => void;
}

interface CanvasSize {
  width: number;
  height: number;
}

interface GraphTooltip {
  x: number;
  y: number;
  title: string;
  detail?: string;
}

const MIN_CANVAS_WIDTH = 760;
const CANVAS_HEIGHT = 620;

function shortLabel(value?: string, length = 26): string {
  if (!value) {
    return "";
  }
  return value.length > length ? `${value.slice(0, length - 1)}...` : value;
}

function nodeClassName(
  node: WorkbenchNode,
  selectedNodeId: string | null,
  selectedEdgeId: string | null,
  highlightedNodeIds: Set<string>,
) {
  const hasSelection = Boolean(selectedNodeId || selectedEdgeId);
  return [
    "force-graph-node",
    `force-node-${node.type}`,
    selectedNodeId === node.id ? "is-selected" : "",
    highlightedNodeIds.has(node.id) && selectedNodeId !== node.id ? "is-connected" : "",
    hasSelection && !highlightedNodeIds.has(node.id) ? "is-dimmed" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function edgeClassName(
  edge: ForceGraphEdge,
  selectedNodeId: string | null,
  selectedEdgeId: string | null,
) {
  const [sourceId, targetId] = edgeEndpointIds(edge);
  const isSelected = selectedEdgeId === edge.id;
  const isConnectedToNode =
    Boolean(selectedNodeId) && (sourceId === selectedNodeId || targetId === selectedNodeId);
  const hasSelection = Boolean(selectedNodeId || selectedEdgeId);
  return [
    "force-graph-edge",
    `force-edge-${edge.type}`,
    isSelected ? "is-selected" : "",
    isConnectedToNode ? "is-connected" : "",
    hasSelection && !isSelected && !isConnectedToNode ? "is-dimmed" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function shapeForNode(node: ForceGraphNode) {
  if (node.type === "agent") {
    return <circle r={node.radius} />;
  }
  if (node.type === "risk") {
    const r = node.radius;
    return <polygon points={`0,${-r} ${r},0 0,${r} ${-r},0`} />;
  }
  if (node.type === "asset") {
    const width = node.radius * 2.45;
    const height = node.radius * 1.35;
    return <rect height={height} rx={height / 2} width={width} x={-width / 2} y={-height / 2} />;
  }
  const width = node.radius * 2.65;
  const height = node.radius * 1.45;
  return <rect height={height} rx={8} width={width} x={-width / 2} y={-height / 2} />;
}

export function DailyGraphCanvas({
  graph,
  selectedDate,
  previousDate,
  nextDate,
  selectedNodeId,
  selectedEdgeId,
  onSelectDate,
  onSelectNode,
  onSelectEdge,
}: DailyGraphCanvasProps) {
  const { t } = useI18n();
  const frameRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const viewportRef = useRef<SVGGElement | null>(null);
  const edgeLayerRef = useRef<SVGGElement | null>(null);
  const nodeLayerRef = useRef<SVGGElement | null>(null);
  const simulationRef = useRef<Simulation<ForceGraphNode, ForceGraphEdge> | null>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [canvasSize, setCanvasSize] = useState<CanvasSize>({
    width: Math.max(MIN_CANVAS_WIDTH, graph.width),
    height: CANVAS_HEIGHT,
  });
  const [zoomTransform, setZoomTransform] = useState<ZoomTransform>(zoomIdentity);
  const [tooltip, setTooltip] = useState<GraphTooltip | null>(null);

  const forceGraph = useMemo(
    () => toForceGraph(graph, canvasSize.width, canvasSize.height),
    [canvasSize.height, canvasSize.width, graph],
  );

  const nodeById = useMemo(
    () => new Map(forceGraph.nodes.map((node) => [node.id, node])),
    [forceGraph.nodes],
  );

  const highlightedNodeIds = useMemo(() => {
    if (selectedNodeId) {
      return connectedNodeIds(forceGraph.edges, selectedNodeId);
    }
    return selectedEdgeNodeIds(forceGraph.edges, selectedEdgeId);
  }, [forceGraph.edges, selectedEdgeId, selectedNodeId]);

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

  const showNodeTooltip = useCallback(
    (event: React.MouseEvent, node: ForceGraphNode) => {
      const frame = frameRef.current?.getBoundingClientRect();
      const x = frame ? event.clientX - frame.left + 12 : event.clientX;
      const y = frame ? event.clientY - frame.top + 12 : event.clientY;
      setTooltip({
        x,
        y,
        title: displayNodeLabel(node),
        detail: [displayNodeSubtitle(node), node.detail].filter(Boolean).join(" - "),
      });
    },
    [t],
  );

  const showEdgeTooltip = useCallback(
    (event: React.MouseEvent, edge: ForceGraphEdge) => {
      const [sourceId, targetId] = edgeEndpointIds(edge);
      const source = nodeById.get(sourceId);
      const target = nodeById.get(targetId);
      const frame = frameRef.current?.getBoundingClientRect();
      const x = frame ? event.clientX - frame.left + 12 : event.clientX;
      const y = frame ? event.clientY - frame.top + 12 : event.clientY;
      setTooltip({
        x,
        y,
        title: t("workbench.relationship"),
        detail: `${source ? displayNodeLabel(source) : sourceId} -> ${
          target ? displayNodeLabel(target) : targetId
        }`,
      });
    },
    [nodeById, t],
  );

  const clearSelection = useCallback(() => {
    onSelectNode(null);
    onSelectEdge(null);
  }, [onSelectEdge, onSelectNode]);

  const resetView = useCallback(() => {
    const svg = svgRef.current;
    const zoomBehavior = zoomBehaviorRef.current;
    if (!svg || !zoomBehavior) {
      setZoomTransform(zoomIdentity);
      return;
    }
    select(svg).call(zoomBehavior.transform, zoomIdentity);
  }, []);

  const fitView = useCallback(() => {
    const svg = svgRef.current;
    const zoomBehavior = zoomBehaviorRef.current;
    if (!svg || !zoomBehavior) {
      return;
    }
    const fitted = zoomIdentity.translate(canvasSize.width * 0.04, canvasSize.height * 0.03).scale(0.92);
    select(svg).call(zoomBehavior.transform, fitted);
  }, [canvasSize.height, canvasSize.width]);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width || graph.width;
      setCanvasSize({
        width: Math.max(MIN_CANVAS_WIDTH, Math.floor(width)),
        height: CANVAS_HEIGHT,
      });
    });
    observer.observe(frame);
    return () => observer.disconnect();
  }, [graph.width]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) {
      return;
    }
    const zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.45, 2.4])
      .on("zoom", (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        setZoomTransform(event.transform);
      });
    zoomBehaviorRef.current = zoomBehavior;
    select(svg).call(zoomBehavior);
    return () => {
      select(svg).on(".zoom", null);
    };
  }, []);

  useEffect(() => {
    const nodeLayer = nodeLayerRef.current;
    const edgeLayer = edgeLayerRef.current;
    if (!nodeLayer || !edgeLayer) {
      return;
    }

    simulationRef.current?.stop();

    const edgeSelection = select(edgeLayer)
      .selectAll<SVGLineElement, ForceGraphEdge>(".force-graph-edge")
      .data(forceGraph.edges, (edge) => edge?.id || "");
    const edgeHitSelection = select(edgeLayer)
      .selectAll<SVGLineElement, ForceGraphEdge>(".force-graph-edge-hit")
      .data(forceGraph.edges, (edge) => edge?.id || "");
    const nodeSelection = select(nodeLayer)
      .selectAll<SVGGElement, ForceGraphNode>(".force-graph-node")
      .data(forceGraph.nodes, (node) => node?.id || "");

    const ticked = () => {
      const updateEdge = (
        selection: typeof edgeSelection | typeof edgeHitSelection,
      ) => {
        selection
        .attr("x1", (edge) => {
          const [sourceId] = edgeEndpointIds(edge);
          return nodeById.get(sourceId)?.x ?? 0;
        })
        .attr("y1", (edge) => {
          const [sourceId] = edgeEndpointIds(edge);
          return nodeById.get(sourceId)?.y ?? 0;
        })
        .attr("x2", (edge) => {
          const [, targetId] = edgeEndpointIds(edge);
          return nodeById.get(targetId)?.x ?? 0;
        })
        .attr("y2", (edge) => {
          const [, targetId] = edgeEndpointIds(edge);
          return nodeById.get(targetId)?.y ?? 0;
        });
      };

      updateEdge(edgeSelection);
      updateEdge(edgeHitSelection);

      nodeSelection.attr("transform", (node) => `translate(${node.x ?? node.initialX}, ${node.y ?? node.initialY})`);
    };

    const simulation = forceSimulation<ForceGraphNode>(forceGraph.nodes)
      .force(
        "link",
        forceLink<ForceGraphNode, ForceGraphEdge>(forceGraph.edges)
          .id((node) => node.id)
          .distance((edge) => (edge.type === "agent_attention" ? 124 : 156))
          .strength(0.34),
      )
      .force("charge", forceManyBody<ForceGraphNode>().strength(-520))
      .force("collide", forceCollide<ForceGraphNode>().radius((node) => node.radius + 34).iterations(2))
      .force("x", forceX<ForceGraphNode>((node) => nodeAnchor(node, canvasSize.width, canvasSize.height)[0]).strength(0.11))
      .force("y", forceY<ForceGraphNode>((node) => nodeAnchor(node, canvasSize.width, canvasSize.height)[1]).strength(0.13))
      .on("tick", ticked);

    const dragBehavior = drag<SVGGElement, ForceGraphNode>()
      .on("start", (event: D3DragEvent<SVGGElement, ForceGraphNode, ForceGraphNode>, node) => {
        if (!event.active) {
          simulation.alphaTarget(0.24).restart();
        }
        node.fx = node.x;
        node.fy = node.y;
      })
      .on("drag", (event: D3DragEvent<SVGGElement, ForceGraphNode, ForceGraphNode>, node) => {
        node.fx = event.x;
        node.fy = event.y;
        ticked();
      })
      .on("end", (event: D3DragEvent<SVGGElement, ForceGraphNode, ForceGraphNode>, node) => {
        if (!event.active) {
          simulation.alphaTarget(0);
        }
        node.fx = null;
        node.fy = null;
      });

    nodeSelection.call(dragBehavior);
    simulationRef.current = simulation;
    ticked();

    return () => {
      simulation.stop();
      nodeSelection.on(".drag", null);
    };
  }, [canvasSize.height, canvasSize.width, forceGraph.edges, forceGraph.nodes, nodeById]);

  return (
    <section className="workbench-card workbench-graph-card">
      <div className="workbench-card-header">
        <div>
          <p className="pixel-kicker workbench-module-kicker">
            {t("workbench.graphKicker")}
          </p>
          <h2>{t("workbench.graphTitle")}</h2>
          <p className="muted">
            {t("workbench.graphHelp")}
          </p>
        </div>
        <div className="graph-date-controls">
          <span className="tag">{selectedDate}</span>
          <div className="button-row">
            <button
              className="button secondary"
              disabled={!previousDate}
              onClick={() => previousDate && onSelectDate(previousDate)}
              type="button"
            >
              {t("workbench.previous")}
            </button>
            <button
              className="button secondary"
              disabled={!nextDate}
              onClick={() => nextDate && onSelectDate(nextDate)}
              type="button"
            >
              {t("workbench.next")}
            </button>
            {selectedNodeId || selectedEdgeId ? (
              <button
                className="button secondary"
                onClick={clearSelection}
                type="button"
              >
                {t("workbench.clearNode")}
              </button>
            ) : null}
          </div>
        </div>
      </div>
      <GraphLegend />
      <div className="force-graph-controls">
        <span className="muted">{t("workbench.zoomPanHint")}</span>
        <div className="button-row">
          <button className="button secondary" onClick={fitView} type="button">
            {t("workbench.fitView")}
          </button>
          <button className="button secondary" onClick={resetView} type="button">
            {t("workbench.resetView")}
          </button>
        </div>
      </div>
      <div className="workbench-svg-frame force-graph-frame" ref={frameRef}>
        <svg
          className="workbench-svg force-graph-svg"
          role="group"
          ref={svgRef}
          viewBox={`0 0 ${canvasSize.width} ${canvasSize.height}`}
          aria-label={t("workbench.graphAria")}
        >
          <defs>
            <marker
              id="force-graph-arrow"
              markerHeight="4"
              markerWidth="4"
              orient="auto"
              refX="4"
              refY="2"
            >
              <path d="M0,0 L4,2 L0,4 z" className="workbench-arrow" />
            </marker>
          </defs>
          <rect
            className="force-graph-hit-area"
            height={canvasSize.height}
            onClick={clearSelection}
            width={canvasSize.width}
          />
          <g className="force-graph-viewport" ref={viewportRef} transform={zoomTransform.toString()}>
            <g className="workbench-edges force-graph-edges" ref={edgeLayerRef}>
              {forceGraph.edges.map((edge) => {
                const source = nodeById.get(edge.sourceId);
                const target = nodeById.get(edge.targetId);
                const edgeAccessibleLabel = `${t("workbench.relationship")}: ${
                  source ? displayNodeLabel(source) : edge.sourceId
                } ${t("common.to")} ${
                  target ? displayNodeLabel(target) : edge.targetId
                }`;
                return (
                  <g key={edge.id}>
                    <line
                      className="force-graph-edge-hit"
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelectEdge(edge.id);
                        onSelectNode(null);
                      }}
                      onMouseEnter={(event) => showEdgeTooltip(event, edge)}
                      onMouseLeave={() => setTooltip(null)}
                      onMouseMove={(event) => showEdgeTooltip(event, edge)}
                      x1={source?.initialX || 0}
                      x2={target?.initialX || 0}
                      y1={source?.initialY || 0}
                      y2={target?.initialY || 0}
                    />
                    <line
                      aria-label={edgeAccessibleLabel}
                      aria-pressed={selectedEdgeId === edge.id}
                      className={edgeClassName(edge, selectedNodeId, selectedEdgeId)}
                      markerEnd="url(#force-graph-arrow)"
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelectEdge(edge.id);
                        onSelectNode(null);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSelectEdge(edge.id);
                          onSelectNode(null);
                        }
                      }}
                      onMouseEnter={(event) => showEdgeTooltip(event, edge)}
                      onMouseLeave={() => setTooltip(null)}
                      onMouseMove={(event) => showEdgeTooltip(event, edge)}
                      role="button"
                      tabIndex={0}
                      x1={source?.initialX || 0}
                      x2={target?.initialX || 0}
                      y1={source?.initialY || 0}
                      y2={target?.initialY || 0}
                    />
                  </g>
                );
              })}
            </g>
            <g className="workbench-nodes force-graph-nodes" ref={nodeLayerRef}>
              {forceGraph.nodes.map((node) => (
                <g
                  aria-label={[
                    displayNodeLabel(node),
                    displayNodeSubtitle(node),
                  ].filter(Boolean).join(": ")}
                  aria-pressed={selectedNodeId === node.id}
                  className={nodeClassName(node, selectedNodeId, selectedEdgeId, highlightedNodeIds)}
                  key={node.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelectNode(node.id);
                    onSelectEdge(null);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectNode(node.id);
                      onSelectEdge(null);
                    }
                  }}
                  onMouseEnter={(event) => showNodeTooltip(event, node)}
                  onMouseLeave={() => setTooltip(null)}
                  onMouseMove={(event) => showNodeTooltip(event, node)}
                  role="button"
                  tabIndex={0}
                  transform={`translate(${node.initialX} ${node.initialY})`}
                >
                  <circle className="force-node-hit-target" r={Math.max(38, node.radius + 28)} />
                  {shapeForNode(node)}
                  <g className="force-node-label" transform={`translate(0 ${node.radius + 18})`}>
                    <text className="node-label">
                      {shortLabel(displayNodeLabel(node), 28)}
                    </text>
                    {node.subtitle ? (
                      <text className="node-subtitle" y="18">
                        {shortLabel(displayNodeSubtitle(node), 26)}
                      </text>
                    ) : null}
                  </g>
                </g>
              ))}
            </g>
          </g>
        </svg>
        {tooltip ? (
          <div className="force-graph-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
            <strong>{tooltip.title}</strong>
            {tooltip.detail ? <span>{tooltip.detail}</span> : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

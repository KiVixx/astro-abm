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
import type {
  WorkbenchGraph,
  WorkbenchNode,
  WorkbenchNodeType,
} from "@/lib/workbenchGraph";
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
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
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

type RelationshipViewMode = "focused" | "all";

const MIN_CANVAS_WIDTH = 760;
const CANVAS_HEIGHT = 620;
const SIMULATION_MAX_MS = 3000;
const ALL_NODE_TYPES: WorkbenchNodeType[] = [
  "agent",
  "astro",
  "stress",
  "volatility",
  "liquidity",
  "data_quality",
  "asset",
  "risk",
];

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
  selectedNodeId,
  selectedEdgeId,
  onSelectNode,
  onSelectEdge,
}: DailyGraphCanvasProps) {
  const { t } = useI18n();
  const frameRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const viewportRef = useRef<SVGGElement | null>(null);
  const expandButtonRef = useRef<HTMLButtonElement | null>(null);
  const edgeLayerRef = useRef<SVGGElement | null>(null);
  const nodeLayerRef = useRef<SVGGElement | null>(null);
  const simulationRef = useRef<Simulation<ForceGraphNode, ForceGraphEdge> | null>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const lastAutoFocusedNodeRef = useRef<string | null>(null);
  const [canvasSize, setCanvasSize] = useState<CanvasSize>({
    width: Math.max(MIN_CANVAS_WIDTH, graph.width),
    height: CANVAS_HEIGHT,
  });
  const [zoomTransform, setZoomTransform] = useState<ZoomTransform>(zoomIdentity);
  const [tooltip, setTooltip] = useState<GraphTooltip | null>(null);
  const [relationshipView, setRelationshipView] = useState<RelationshipViewMode>("focused");
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeNodeTypes, setActiveNodeTypes] = useState<Set<WorkbenchNodeType>>(
    () => new Set(ALL_NODE_TYPES),
  );

  const forceGraph = useMemo(
    () => toForceGraph(graph, canvasSize.width, canvasSize.height),
    [canvasSize.height, canvasSize.width, graph],
  );
  const visibleNodes = useMemo(
    () => forceGraph.nodes.filter((node) => activeNodeTypes.has(node.type)),
    [activeNodeTypes, forceGraph.nodes],
  );
  const visibleNodeIds = useMemo(
    () => new Set(visibleNodes.map((node) => node.id)),
    [visibleNodes],
  );
  const visibleEdges = useMemo(() => {
    const edgesForVisibleNodes = forceGraph.edges.filter((edge) => {
      const [sourceId, targetId] = edgeEndpointIds(edge);
      return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId);
    });
    if (relationshipView === "all") {
      return edgesForVisibleNodes;
    }
    if (selectedEdgeId) {
      return edgesForVisibleNodes.filter((edge) => edge.id === selectedEdgeId);
    }
    if (selectedNodeId) {
      return edgesForVisibleNodes.filter((edge) => {
        const [sourceId, targetId] = edgeEndpointIds(edge);
        return sourceId === selectedNodeId || targetId === selectedNodeId;
      });
    }
    return edgesForVisibleNodes.filter((edge) => edge.type !== "agent_attention");
  }, [forceGraph.edges, relationshipView, selectedEdgeId, selectedNodeId, visibleNodeIds]);
  const visibleEdgeIds = useMemo(
    () => new Set(visibleEdges.map((edge) => edge.id)),
    [visibleEdges],
  );
  const graphKeyboardIds = useMemo(
    () => [
      ...visibleNodes.map((node) => `node:${node.id}`),
      ...visibleEdges.map((edge) => `edge:${edge.id}`),
    ],
    [visibleEdges, visibleNodes],
  );
  const [keyboardFocusId, setKeyboardFocusId] = useState(
    () => graphKeyboardIds[0] || "",
  );

  const nodeById = useMemo(
    () => new Map(forceGraph.nodes.map((node) => [node.id, node])),
    [forceGraph.nodes],
  );
  const selectedNodeForStatus = selectedNodeId ? nodeById.get(selectedNodeId) : undefined;

  const displayNodeType = (node: WorkbenchNode) => {
    const typeKeys: Record<WorkbenchNode["type"], string> = {
      agent: "legend.agent",
      astro: "legend.astro",
      stress: "legend.market",
      volatility: "legend.market",
      liquidity: "legend.market",
      data_quality: "legend.data",
      asset: "legend.asset",
      risk: "legend.risk",
    };
    return t(typeKeys[node.type]);
  };

  const highlightedNodeIds = useMemo(() => {
    if (selectedNodeId) {
      return connectedNodeIds(forceGraph.edges, selectedNodeId);
    }
    return selectedEdgeNodeIds(forceGraph.edges, selectedEdgeId);
  }, [forceGraph.edges, selectedEdgeId, selectedNodeId]);

  useEffect(() => {
    const selectedId = selectedNodeId
      ? `node:${selectedNodeId}`
      : selectedEdgeId
        ? `edge:${selectedEdgeId}`
        : null;
    setKeyboardFocusId((current) => {
      if (selectedId && graphKeyboardIds.includes(selectedId)) {
        return selectedId;
      }
      return graphKeyboardIds.includes(current) ? current : graphKeyboardIds[0] || "";
    });
  }, [graphKeyboardIds, selectedEdgeId, selectedNodeId]);

  const moveGraphFocus = (
    event: React.KeyboardEvent<SVGElement>,
    currentId: string,
  ) => {
    let nextIndex: number | null = null;
    const currentIndex = graphKeyboardIds.indexOf(currentId);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = Math.min(graphKeyboardIds.length - 1, currentIndex + 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = Math.max(0, currentIndex - 1);
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = graphKeyboardIds.length - 1;
    }
    if (nextIndex === null || nextIndex === currentIndex || nextIndex < 0) {
      return;
    }
    event.preventDefault();
    const nextId = graphKeyboardIds[nextIndex];
    setKeyboardFocusId(nextId);
    requestAnimationFrame(() => {
      const nextElement = Array.from(
        svgRef.current?.querySelectorAll<SVGElement>("[data-graph-keyboard-id]") || [],
      ).find((element) => element.dataset.graphKeyboardId === nextId);
      nextElement?.focus();
    });
  };

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
    if (node.type === "agent") {
      return formatEnumLabel(t, "agent_level", node.subtitle);
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

  useEffect(() => {
    if (!isExpanded) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => expandButtonRef.current?.focus());
    const exitExpandedView = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsExpanded(false);
      }
    };
    document.addEventListener("keydown", exitExpandedView);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", exitExpandedView);
    };
  }, [isExpanded]);

  useEffect(() => {
    setTooltip(null);
    resetView();
  }, [resetView, selectedDate]);

  const zoomViewBy = useCallback((factor: number) => {
    const svg = svgRef.current;
    const zoomBehavior = zoomBehaviorRef.current;
    if (!svg || !zoomBehavior) {
      return;
    }
    select(svg).call(zoomBehavior.scaleBy, factor);
  }, []);

  const focusNodeInView = useCallback((nodeId: string) => {
    const svg = svgRef.current;
    const zoomBehavior = zoomBehaviorRef.current;
    const node = nodeById.get(nodeId);
    if (!svg || !zoomBehavior || !node) {
      return;
    }
    const scale = Math.max(zoomTransform.k, canvasSize.width <= MIN_CANVAS_WIDTH ? 1.35 : 1.1);
    const nodeX = node.x ?? node.initialX;
    const nodeY = node.y ?? node.initialY;
    const focused = zoomIdentity
      .translate(
        canvasSize.width / 2 - nodeX * scale,
        canvasSize.height / 2 - nodeY * scale,
      )
      .scale(scale);
    select(svg).call(zoomBehavior.transform, focused);
  }, [canvasSize.height, canvasSize.width, nodeById, zoomTransform.k]);

  useEffect(() => {
    if (!selectedNodeId) {
      lastAutoFocusedNodeRef.current = null;
      return;
    }
    if (lastAutoFocusedNodeRef.current === selectedNodeId) {
      return;
    }
    lastAutoFocusedNodeRef.current = selectedNodeId;
    const animationFrame = requestAnimationFrame(() => focusNodeInView(selectedNodeId));
    return () => cancelAnimationFrame(animationFrame);
  }, [focusNodeInView, selectedNodeId]);

  const selectNodeFromNavigator = (nodeId: string) => {
    if (!nodeId) {
      clearSelection();
      return;
    }
    onSelectNode(nodeId);
    onSelectEdge(null);
  };

  const toggleNodeTypes = (nodeTypes: WorkbenchNodeType[]) => {
    setActiveNodeTypes((current) => {
      const next = new Set(current);
      const shouldHide = nodeTypes.every((type) => current.has(type));
      nodeTypes.forEach((type) => {
        if (shouldHide) {
          next.delete(type);
        } else {
          next.add(type);
        }
      });
      return next.size ? next : current;
    });
    if (selectedNodeForStatus && nodeTypes.includes(selectedNodeForStatus.type)) {
      clearSelection();
    } else if (selectedEdgeId) {
      onSelectEdge(null);
    }
  };

  const fitView = useCallback(() => {
    const svg = svgRef.current;
    const zoomBehavior = zoomBehaviorRef.current;
    if (!svg || !zoomBehavior || !visibleNodes.length) {
      return;
    }
    const horizontalLabelRoom = 112;
    const verticalLabelRoom = 58;
    const minX = Math.min(
      ...visibleNodes.map((node) => (node.x ?? node.initialX) - node.radius - horizontalLabelRoom),
    );
    const maxX = Math.max(
      ...visibleNodes.map((node) => (node.x ?? node.initialX) + node.radius + horizontalLabelRoom),
    );
    const minY = Math.min(
      ...visibleNodes.map((node) => (node.y ?? node.initialY) - node.radius - verticalLabelRoom),
    );
    const maxY = Math.max(
      ...visibleNodes.map((node) => (node.y ?? node.initialY) + node.radius + verticalLabelRoom),
    );
    const boundsWidth = Math.max(1, maxX - minX);
    const boundsHeight = Math.max(1, maxY - minY);
    const scale = Math.max(
      0.45,
      Math.min(1.2, canvasSize.width / boundsWidth, canvasSize.height / boundsHeight),
    );
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const fitted = zoomIdentity
      .translate(
        canvasSize.width / 2 - centerX * scale,
        canvasSize.height / 2 - centerY * scale,
      )
      .scale(scale);
    select(svg).call(zoomBehavior.transform, fitted);
  }, [canvasSize.height, canvasSize.width, visibleNodes]);

  const showAllNodeTypes = () => {
    setActiveNodeTypes(new Set(ALL_NODE_TYPES));
  };

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
    const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
      ?? false;

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
      .alphaDecay(0.04)
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
      .force("y", forceY<ForceGraphNode>((node) => nodeAnchor(node, canvasSize.width, canvasSize.height)[1]).strength(0.13));

    if (prefersReducedMotion) {
      simulation.stop();
      simulation.tick(160);
      ticked();
    } else {
      simulation.on("tick", ticked);
    }
    const simulationStopTimer = prefersReducedMotion
      ? null
      : window.setTimeout(() => {
          simulation.alphaTarget(0).stop();
          ticked();
        }, SIMULATION_MAX_MS);

    const dragBehavior = drag<SVGGElement, ForceGraphNode>()
      .on("start", (event: D3DragEvent<SVGGElement, ForceGraphNode, ForceGraphNode>, node) => {
        if (!prefersReducedMotion && !event.active) {
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
        if (!prefersReducedMotion && !event.active) {
          simulation.alphaTarget(0);
        }
        node.fx = null;
        node.fy = null;
      });

    nodeSelection.call(dragBehavior);
    simulationRef.current = simulation;
    ticked();

    return () => {
      if (simulationStopTimer !== null) {
        window.clearTimeout(simulationStopTimer);
      }
      simulation.stop();
      nodeSelection.on(".drag", null);
    };
  }, [canvasSize.height, canvasSize.width, forceGraph.edges, forceGraph.nodes, nodeById]);

  return (
    <section
      aria-labelledby="context-graph-title"
      aria-modal={isExpanded || undefined}
      className={`workbench-card workbench-graph-card ${isExpanded ? "is-expanded" : ""}`}
      role={isExpanded ? "dialog" : undefined}
    >
      <div className="workbench-card-header">
        <div>
          <p className="pixel-kicker workbench-module-kicker">
            {t("workbench.graphKicker")}
          </p>
          <h2 id="context-graph-title">{t("workbench.graphTitle")}</h2>
          <p className="muted">
            {t("workbench.graphHelp")}
          </p>
        </div>
        <div className="graph-date-controls">
          <span className="tag">{selectedDate}</span>
          <button
            aria-expanded={isExpanded}
            className="button secondary"
            onClick={() => {
              setIsExpanded((current) => !current);
              requestAnimationFrame(resetView);
            }}
            ref={expandButtonRef}
            type="button"
          >
            {isExpanded ? t("workbench.exitExpandedGraph") : t("workbench.expandGraph")}
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
      <GraphLegend
        activeNodeTypes={activeNodeTypes}
        onToggleNodeTypes={toggleNodeTypes}
      />
      <div className="graph-relationship-toolbar">
        <div
          aria-label={t("workbench.relationshipView")}
          className="graph-relationship-segments"
          role="group"
        >
          <button
            aria-pressed={relationshipView === "focused"}
            className={relationshipView === "focused" ? "is-active" : ""}
            onClick={() => setRelationshipView("focused")}
            type="button"
          >
            {t("workbench.focusedRelationships")}
          </button>
          <button
            aria-pressed={relationshipView === "all"}
            className={relationshipView === "all" ? "is-active" : ""}
            onClick={() => setRelationshipView("all")}
            type="button"
          >
            {t("workbench.allRelationships")}
          </button>
        </div>
        <div aria-live="polite" className="graph-focus-summary">
          <strong>
            {selectedNodeForStatus
              ? `${t("workbench.focusedOn")}: ${displayNodeLabel(selectedNodeForStatus)}`
              : selectedEdgeId
                ? `${t("workbench.focusedOn")}: ${t("workbench.selectedRelationship")}`
                : relationshipView === "focused"
                  ? t("workbench.focusedRelationshipsHelp")
                  : t("workbench.allRelationshipsHelp")}
          </strong>
          <span>
            {visibleNodes.length}/{forceGraph.nodes.length} {t("workbench.nodesVisible")} ·{" "}
            {visibleEdges.length}/{forceGraph.edges.length} {t("workbench.relationshipsVisible")}
          </span>
        </div>
      </div>
      <div className="force-graph-controls">
        <div className="graph-node-navigator">
          <label htmlFor="graph-node-navigator">{t("workbench.findNode")}</label>
          <select
            id="graph-node-navigator"
            onChange={(event) => selectNodeFromNavigator(event.target.value)}
            value={selectedNodeId || ""}
          >
            <option value="">{t("workbench.chooseNode")}</option>
            {visibleNodes.map((node) => (
              <option key={node.id} value={node.id}>
                {displayNodeLabel(node)} ({displayNodeType(node)})
              </option>
            ))}
          </select>
          <span className="muted">{t("workbench.zoomPanHint")}</span>
        </div>
        <div className="button-row">
          <button
            aria-label={t("workbench.zoomIn")}
            className="button secondary graph-zoom-button"
            onClick={() => zoomViewBy(1.25)}
            title={t("workbench.zoomIn")}
            type="button"
          >
            +
          </button>
          <button
            aria-label={t("workbench.zoomOut")}
            className="button secondary graph-zoom-button"
            onClick={() => zoomViewBy(0.8)}
            title={t("workbench.zoomOut")}
            type="button"
          >
            -
          </button>
          {activeNodeTypes.size < ALL_NODE_TYPES.length ? (
            <button className="button secondary" onClick={showAllNodeTypes} type="button">
              {t("workbench.showAllNodeTypes")}
            </button>
          ) : null}
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
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              if (isExpanded) {
                setIsExpanded(false);
              } else {
                clearSelection();
              }
            }
          }}
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
                const keyboardId = `edge:${edge.id}`;
                const isVisible = visibleEdgeIds.has(edge.id);
                const source = nodeById.get(edge.sourceId);
                const target = nodeById.get(edge.targetId);
                const edgeAccessibleLabel = `${t("workbench.relationship")}: ${
                  source ? displayNodeLabel(source) : edge.sourceId
                } ${t("common.to")} ${
                  target ? displayNodeLabel(target) : edge.targetId
                }`;
                return (
                  <g
                    aria-hidden={!isVisible}
                    className={`force-graph-edge-group ${isVisible ? "" : "is-filtered"}`}
                    key={edge.id}
                  >
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
                      data-graph-keyboard-id={keyboardId}
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
                          return;
                        }
                        moveGraphFocus(event, keyboardId);
                      }}
                      onFocus={() => setKeyboardFocusId(keyboardId)}
                      onMouseEnter={(event) => showEdgeTooltip(event, edge)}
                      onMouseLeave={() => setTooltip(null)}
                      onMouseMove={(event) => showEdgeTooltip(event, edge)}
                      role="button"
                      tabIndex={isVisible && keyboardFocusId === keyboardId ? 0 : -1}
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
              {forceGraph.nodes.map((node) => {
                const keyboardId = `node:${node.id}`;
                const isVisible = visibleNodeIds.has(node.id);
                return (
                <g
                  aria-hidden={!isVisible}
                  aria-label={[
                    displayNodeLabel(node),
                    displayNodeSubtitle(node),
                  ].filter(Boolean).join(": ")}
                  aria-pressed={selectedNodeId === node.id}
                  className={`${nodeClassName(node, selectedNodeId, selectedEdgeId, highlightedNodeIds)} ${isVisible ? "" : "is-filtered"}`}
                  data-graph-keyboard-id={keyboardId}
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
                      return;
                    }
                    moveGraphFocus(event, keyboardId);
                  }}
                  onFocus={() => setKeyboardFocusId(keyboardId)}
                  onMouseEnter={(event) => showNodeTooltip(event, node)}
                  onMouseLeave={() => setTooltip(null)}
                  onMouseMove={(event) => showNodeTooltip(event, node)}
                  role="button"
                  tabIndex={isVisible && keyboardFocusId === keyboardId ? 0 : -1}
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
                );
              })}
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

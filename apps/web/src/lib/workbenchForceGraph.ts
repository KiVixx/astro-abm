import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";
import type {
  WorkbenchEdge,
  WorkbenchGraph,
  WorkbenchNode,
  WorkbenchNodeType,
} from "./workbenchGraph";

export interface ForceGraphNode
  extends Omit<WorkbenchNode, "x" | "y">,
    SimulationNodeDatum {
  x: number;
  y: number;
  radius: number;
  initialX: number;
  initialY: number;
}

export interface ForceGraphEdge extends SimulationLinkDatum<ForceGraphNode> {
  id: string;
  source: string | ForceGraphNode;
  target: string | ForceGraphNode;
  sourceId: string;
  targetId: string;
  type: WorkbenchEdge["type"];
  label?: string;
}

const TYPE_RADIUS: Record<WorkbenchNodeType, number> = {
  agent: 9,
  astro: 10,
  stress: 11,
  volatility: 11,
  liquidity: 11,
  data_quality: 10,
  asset: 10,
  risk: 9,
};

function anchorForType(type: WorkbenchNodeType, width: number, height: number) {
  const centerY = height / 2;
  const anchors: Record<WorkbenchNodeType, [number, number]> = {
    agent: [width * 0.18, centerY],
    astro: [width * 0.49, height * 0.24],
    stress: [width * 0.5, height * 0.4],
    volatility: [width * 0.5, height * 0.56],
    liquidity: [width * 0.5, height * 0.72],
    data_quality: [width * 0.5, height * 0.86],
    asset: [width * 0.78, height * 0.35],
    risk: [width * 0.78, height * 0.68],
  };
  return anchors[type];
}

export function nodeRadius(type: WorkbenchNodeType): number {
  return TYPE_RADIUS[type] || 38;
}

export function nodeAnchor(node: ForceGraphNode, width: number, height: number) {
  return anchorForType(node.type, width, height);
}

export function toForceGraph(
  graph: WorkbenchGraph,
  width: number,
  height: number,
): { nodes: ForceGraphNode[]; edges: ForceGraphEdge[] } {
  const nodes = graph.nodes.map((node) => {
    const initialX = Math.max(80, Math.min(width - 80, (node.x / graph.width) * width));
    const initialY = Math.max(80, Math.min(height - 80, (node.y / graph.height) * height));
    return {
      ...node,
      initialX,
      initialY,
      radius: nodeRadius(node.type),
      x: initialX,
      y: initialY,
    };
  });

  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = graph.edges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => ({
      ...edge,
      sourceId: edge.source,
      targetId: edge.target,
      source: edge.source,
      target: edge.target,
    }));

  return { nodes, edges };
}

export function edgeEndpointIds(edge: ForceGraphEdge | WorkbenchEdge): [string, string] {
  const source =
    typeof edge.source === "string"
      ? edge.source
      : (edge.source as ForceGraphNode).id;
  const target =
    typeof edge.target === "string"
      ? edge.target
      : (edge.target as ForceGraphNode).id;
  return [source, target];
}

export function connectedNodeIds(
  edges: Array<ForceGraphEdge | WorkbenchEdge>,
  nodeId: string | null,
): Set<string> {
  const connected = new Set<string>();
  if (!nodeId) {
    return connected;
  }
  connected.add(nodeId);
  for (const edge of edges) {
    const [source, target] = edgeEndpointIds(edge);
    if (source === nodeId) {
      connected.add(target);
    }
    if (target === nodeId) {
      connected.add(source);
    }
  }
  return connected;
}

export function selectedEdgeNodeIds(
  edges: Array<ForceGraphEdge | WorkbenchEdge>,
  selectedEdgeId: string | null,
): Set<string> {
  const selected = new Set<string>();
  if (!selectedEdgeId) {
    return selected;
  }
  const edge = edges.find((candidate) => candidate.id === selectedEdgeId);
  if (!edge) {
    return selected;
  }
  const [source, target] = edgeEndpointIds(edge);
  selected.add(source);
  selected.add(target);
  return selected;
}

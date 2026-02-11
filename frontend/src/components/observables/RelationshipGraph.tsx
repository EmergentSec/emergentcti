import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useObservableGraph } from '@/hooks/useRelationships';
import { truncate } from '@/lib/utils';
import type { GraphNode, GraphEdge } from '@/types/relationship';

interface RelationshipGraphProps {
  observableId: string;
}

// Node colors by observable type (fill colors for SVG)
const NODE_COLORS: Record<string, string> = {
  'ip-addr': '#a78bfa',       // purple-400
  'domain-name': '#22d3ee',   // cyan-400
  'url': '#4ade80',           // green-400
  'file-hash': '#fbbf24',     // amber-400
  'email-addr': '#f472b6',    // pink-400
  'command-line': '#9ca3af',  // gray-400
  'user-agent': '#9ca3af',
  'certificate': '#9ca3af',
  'asn': '#9ca3af',
  'cidr': '#9ca3af',
};

const NODE_RADIUS = 24;
const GRAPH_WIDTH = 600;
const GRAPH_HEIGHT = 400;

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

function initializePositions(nodes: GraphNode[], centerId: string): SimNode[] {
  const cx = GRAPH_WIDTH / 2;
  const cy = GRAPH_HEIGHT / 2;

  return nodes.map((node, i) => {
    if (node.id === centerId) {
      return { ...node, x: cx, y: cy, vx: 0, vy: 0 };
    }
    // Place other nodes in a circle around center
    const angle = (2 * Math.PI * i) / Math.max(nodes.length - 1, 1);
    const radius = Math.min(GRAPH_WIDTH, GRAPH_HEIGHT) * 0.3;
    return {
      ...node,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      vx: 0,
      vy: 0,
    };
  });
}

function simulateStep(
  nodes: SimNode[],
  edges: GraphEdge[],
  centerId: string
): SimNode[] {
  const result = nodes.map((n) => ({ ...n }));
  const damping = 0.85;
  const repulsion = 3000;
  const attraction = 0.005;
  const gravityStrength = 0.02;
  const cx = GRAPH_WIDTH / 2;
  const cy = GRAPH_HEIGHT / 2;

  // Repulsion between all node pairs
  for (let i = 0; i < result.length; i++) {
    for (let j = i + 1; j < result.length; j++) {
      const dx = result[i].x - result[j].x;
      const dy = result[i].y - result[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = repulsion / (dist * dist);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      result[i].vx += fx;
      result[i].vy += fy;
      result[j].vx -= fx;
      result[j].vy -= fy;
    }
  }

  // Attraction along edges
  const nodeMap = new Map(result.map((n) => [n.id, n]));
  for (const edge of edges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;

    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const force = dist * attraction;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;

    source.vx += fx;
    source.vy += fy;
    target.vx -= fx;
    target.vy -= fy;
  }

  // Gravity toward center
  for (const node of result) {
    const dx = cx - node.x;
    const dy = cy - node.y;
    node.vx += dx * gravityStrength;
    node.vy += dy * gravityStrength;
  }

  // Apply velocities with damping and boundary constraints
  const padding = NODE_RADIUS + 10;
  for (const node of result) {
    // Pin center node more strongly
    if (node.id === centerId) {
      node.vx *= 0.1;
      node.vy *= 0.1;
    }

    node.vx *= damping;
    node.vy *= damping;
    node.x += node.vx;
    node.y += node.vy;

    // Keep within bounds
    node.x = Math.max(padding, Math.min(GRAPH_WIDTH - padding, node.x));
    node.y = Math.max(padding, Math.min(GRAPH_HEIGHT - padding, node.y));
  }

  return result;
}

export function RelationshipGraph({ observableId }: RelationshipGraphProps) {
  const navigate = useNavigate();
  const { data: graph, isLoading } = useObservableGraph(observableId, 2);
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const animFrameRef = useRef<number>(0);
  const iterationRef = useRef(0);
  const nodesRef = useRef<SimNode[]>([]);

  // Initialize simulation when graph data arrives
  useEffect(() => {
    if (!graph || graph.nodes.length === 0) {
      setSimNodes([]);
      return;
    }

    const initial = initializePositions(graph.nodes, observableId);
    nodesRef.current = initial;
    iterationRef.current = 0;
    setSimNodes(initial);

    const maxIterations = 120;

    const step = () => {
      if (iterationRef.current >= maxIterations) return;

      nodesRef.current = simulateStep(
        nodesRef.current,
        graph.edges,
        observableId
      );
      iterationRef.current++;
      setSimNodes([...nodesRef.current]);

      animFrameRef.current = requestAnimationFrame(step);
    };

    animFrameRef.current = requestAnimationFrame(step);

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [graph, observableId]);

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      if (nodeId !== observableId) {
        navigate(`/observables/${nodeId}`);
      }
    },
    [navigate, observableId]
  );

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Relationship Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="sm" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!graph || graph.nodes.length <= 1) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Relationship Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground italic py-4 text-center">
            No relationships to visualize
          </p>
        </CardContent>
      </Card>
    );
  }

  const nodeMap = new Map(simNodes.map((n) => [n.id, n]));

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Relationship Graph</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border border-border bg-muted/20 overflow-hidden">
          <svg
            width="100%"
            height={GRAPH_HEIGHT}
            viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
            className="select-none"
          >
            <defs>
              {/* Arrow marker for edges */}
              <marker
                id="arrowhead"
                markerWidth="8"
                markerHeight="6"
                refX="8"
                refY="3"
                orient="auto"
              >
                <polygon
                  points="0 0, 8 3, 0 6"
                  fill="#6b7280"
                  opacity="0.6"
                />
              </marker>
            </defs>

            {/* Edges */}
            {graph.edges.map((edge) => {
              const source = nodeMap.get(edge.source);
              const target = nodeMap.get(edge.target);
              if (!source || !target) return null;

              // Calculate edge endpoints (stop at node radius)
              const dx = target.x - source.x;
              const dy = target.y - source.y;
              const dist = Math.sqrt(dx * dx + dy * dy) || 1;
              const offsetX = (dx / dist) * NODE_RADIUS;
              const offsetY = (dy / dist) * NODE_RADIUS;

              const x1 = source.x + offsetX;
              const y1 = source.y + offsetY;
              const x2 = target.x - offsetX;
              const y2 = target.y - offsetY;

              // Midpoint for label
              const mx = (source.x + target.x) / 2;
              const my = (source.y + target.y) / 2;

              return (
                <g key={edge.id}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="#6b7280"
                    strokeWidth="1.5"
                    strokeOpacity="0.4"
                    markerEnd="url(#arrowhead)"
                  />
                  <text
                    x={mx}
                    y={my - 6}
                    textAnchor="middle"
                    fill="#9ca3af"
                    fontSize="9"
                    fontFamily="monospace"
                  >
                    {edge.relationship_type}
                  </text>
                </g>
              );
            })}

            {/* Nodes */}
            {simNodes.map((node) => {
              const isCenter = node.id === observableId;
              const isHovered = node.id === hoveredNode;
              const fillColor = NODE_COLORS[node.type] || '#9ca3af';

              return (
                <g
                  key={node.id}
                  style={{ cursor: isCenter ? 'default' : 'pointer' }}
                  onClick={() => handleNodeClick(node.id)}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  {/* Highlight ring for center node */}
                  {isCenter && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={NODE_RADIUS + 4}
                      fill="none"
                      stroke="#3b82f6"
                      strokeWidth="2"
                      strokeDasharray="4 2"
                      opacity="0.8"
                    />
                  )}

                  {/* Hover ring */}
                  {isHovered && !isCenter && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={NODE_RADIUS + 3}
                      fill="none"
                      stroke={fillColor}
                      strokeWidth="1.5"
                      opacity="0.6"
                    />
                  )}

                  {/* Node circle */}
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={NODE_RADIUS}
                    fill={fillColor}
                    fillOpacity={isCenter ? 0.3 : 0.2}
                    stroke={fillColor}
                    strokeWidth={isCenter ? 2 : 1.5}
                    strokeOpacity={isCenter ? 1 : 0.6}
                  />

                  {/* Type label inside node */}
                  <text
                    x={node.x}
                    y={node.y - 3}
                    textAnchor="middle"
                    fill={fillColor}
                    fontSize="8"
                    fontWeight="600"
                    fontFamily="monospace"
                  >
                    {node.type}
                  </text>

                  {/* Value label below type */}
                  <text
                    x={node.x}
                    y={node.y + 8}
                    textAnchor="middle"
                    fill="#d1d5db"
                    fontSize="7"
                    fontFamily="monospace"
                  >
                    {truncate(node.value, 12)}
                  </text>

                  {/* Full value tooltip on hover */}
                  {isHovered && (
                    <>
                      <rect
                        x={node.x - 80}
                        y={node.y + NODE_RADIUS + 6}
                        width="160"
                        height="22"
                        rx="4"
                        fill="#1f2937"
                        stroke="#374151"
                        strokeWidth="1"
                      />
                      <text
                        x={node.x}
                        y={node.y + NODE_RADIUS + 21}
                        textAnchor="middle"
                        fill="#e5e7eb"
                        fontSize="9"
                        fontFamily="monospace"
                      >
                        {truncate(node.value, 30)}
                      </text>
                    </>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-3 mt-3">
          {Array.from(new Set(graph.nodes.map((n) => n.type))).map((type) => (
            <div key={type} className="flex items-center gap-1.5">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: NODE_COLORS[type] || '#9ca3af' }}
              />
              <span className="text-xs text-muted-foreground">{type}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

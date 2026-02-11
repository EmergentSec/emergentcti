import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useGraph } from '@/hooks/useGraph';
import { useSearch } from '@/hooks/useSearch';
import { useThreatActors } from '@/hooks/useThreatActors';
import { useCampaigns } from '@/hooks/useCampaigns';
import type { GraphNode } from '@/types/graph';
import type { GraphFilters } from '@/api/graph';

// Node colors by entity type
const ENTITY_TYPE_COLORS: Record<string, string> = {
  observable: '#3b82f6',
  threat_actor: '#ef4444',
  campaign: '#f97316',
  technique: '#8b5cf6',
};

// Observable-specific colors (matching RelationshipGraph.tsx)
const OBSERVABLE_TYPE_COLORS: Record<string, string> = {
  'ip-addr': '#a78bfa',
  'domain-name': '#22d3ee',
  url: '#4ade80',
  'file-hash': '#fbbf24',
  'email-addr': '#f472b6',
  'command-line': '#9ca3af',
  'user-agent': '#9ca3af',
  certificate: '#9ca3af',
  asn: '#9ca3af',
  cidr: '#9ca3af',
};

function getNodeColor(node: GraphNode): string {
  if (node.entity_type === 'observable') {
    const obsType = node.metadata?.observable_type as string;
    return OBSERVABLE_TYPE_COLORS[obsType] || ENTITY_TYPE_COLORS.observable;
  }
  return ENTITY_TYPE_COLORS[node.entity_type] || '#9ca3af';
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  observable: 'Observable',
  threat_actor: 'Threat Actor',
  campaign: 'Campaign',
  technique: 'ATT&CK Technique',
};

interface SearchResult {
  id: string;
  entity_type: string;
  label: string;
}

function SearchBar({
  onSelect,
}: {
  onSelect: (entityType: string, entityId: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Search observables
  const { data: searchData, isLoading: searchLoading } = useSearch({
    q: query,
    size: 5,
  });

  // Search threat actors
  const { data: actorsData } = useThreatActors({ name: query, size: 5 });

  // Search campaigns
  const { data: campaignsData } = useCampaigns({ name: query, size: 5 });

  const results: SearchResult[] = useMemo(() => {
    const items: SearchResult[] = [];

    if (searchData?.hits) {
      for (const hit of searchData.hits) {
        items.push({
          id: hit.id,
          entity_type: 'observable',
          label: `${hit.type}: ${hit.value}`,
        });
      }
    }

    if (actorsData?.items) {
      for (const actor of actorsData.items) {
        items.push({
          id: actor.id,
          entity_type: 'threat_actor',
          label: actor.name,
        });
      }
    }

    if (campaignsData?.items) {
      for (const campaign of campaignsData.items) {
        items.push({
          id: campaign.id,
          entity_type: 'campaign',
          label: campaign.name,
        });
      }
    }

    return items;
  }, [searchData, actorsData, campaignsData]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <Input
        placeholder="Search observables, threat actors, campaigns..."
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setShowDropdown(e.target.value.length > 0);
        }}
        onFocus={() => {
          if (query.length > 0) setShowDropdown(true);
        }}
        className="w-full"
      />
      {showDropdown && query.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-card shadow-lg max-h-80 overflow-y-auto">
          {searchLoading ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Searching...
            </div>
          ) : results.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No results found
            </div>
          ) : (
            results.map((result) => (
              <button
                key={`${result.entity_type}-${result.id}`}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-accent transition-colors"
                onClick={() => {
                  onSelect(result.entity_type, result.id);
                  setQuery('');
                  setShowDropdown(false);
                }}
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
                  style={{
                    backgroundColor:
                      ENTITY_TYPE_COLORS[result.entity_type] || '#9ca3af',
                  }}
                />
                <span className="flex-1 truncate">{result.label}</span>
                <Badge variant="outline" className="text-xs shrink-0">
                  {ENTITY_TYPE_LABELS[result.entity_type] || result.entity_type}
                </Badge>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

interface ForceGraphNode {
  id: string;
  label: string;
  entity_type: string;
  metadata: Record<string, unknown>;
  color: string;
  val: number;
  x?: number;
  y?: number;
}

interface ForceGraphLink {
  source: string | ForceGraphNode;
  target: string | ForceGraphNode;
  label: string;
}

interface ForceGraphData {
  nodes: ForceGraphNode[];
  links: ForceGraphLink[];
}

function DetailPanel({
  node,
  onViewDetails,
}: {
  node: ForceGraphNode;
  onViewDetails: () => void;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-2 min-w-0">
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 rounded-full shrink-0"
                style={{ backgroundColor: node.color }}
              />
              <Badge variant="outline" className="text-xs">
                {ENTITY_TYPE_LABELS[node.entity_type] || node.entity_type}
              </Badge>
            </div>
            <p className="text-sm font-medium break-all">{node.label}</p>
            {node.metadata && Object.keys(node.metadata).length > 0 && (
              <div className="space-y-1">
                {Object.entries(node.metadata).map(([key, value]) => {
                  if (value == null) return null;
                  const displayValue = Array.isArray(value)
                    ? value.join(', ')
                    : String(value);
                  if (!displayValue) return null;
                  return (
                    <div
                      key={key}
                      className="flex items-center gap-2 text-xs text-muted-foreground"
                    >
                      <span className="font-medium">{key}:</span>
                      <span className="truncate">{displayValue}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={onViewDetails}>
            View Details
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function GraphExplorerPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read initial entity from URL params if present
  const initialEntityType = searchParams.get('entity_type') || '';
  const initialEntityId = searchParams.get('entity_id') || '';

  const [entityType, setEntityType] = useState(initialEntityType);
  const [entityId, setEntityId] = useState(initialEntityId);
  const [depth, setDepth] = useState(2);
  const [filters, setFilters] = useState<GraphFilters>({
    includeThreatActors: true,
    includeCampaigns: true,
    includeTechniques: true,
  });
  const [selectedNode, setSelectedNode] = useState<ForceGraphNode | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(undefined);

  const { data, isLoading, isError } = useGraph(
    entityType,
    entityId,
    depth,
    filters
  );

  // Build the link-count map for node sizing
  const linkCountMap = useMemo(() => {
    const counts: Record<string, number> = {};
    if (data?.edges) {
      for (const edge of data.edges) {
        counts[edge.source] = (counts[edge.source] || 0) + 1;
        counts[edge.target] = (counts[edge.target] || 0) + 1;
      }
    }
    return counts;
  }, [data]);

  // Transform GraphData into react-force-graph format
  const graphData: ForceGraphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };

    return {
      nodes: data.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        entity_type: n.entity_type,
        metadata: n.metadata,
        color: getNodeColor(n),
        val: Math.max(1, (linkCountMap[n.id] || 0) * 0.5 + 1),
      })),
      links: data.edges.map((e) => ({
        source: e.source,
        target: e.target,
        label: e.relationship_type,
      })),
    };
  }, [data, linkCountMap]);

  const handleEntitySelect = useCallback(
    (type: string, id: string) => {
      setEntityType(type);
      setEntityId(id);
      setSelectedNode(null);
      setSearchParams({ entity_type: type, entity_id: id });
    },
    [setSearchParams]
  );

  const handleNodeClick = useCallback(
    (node: ForceGraphNode) => {
      setSelectedNode(node);
    },
    []
  );

  const handleNodeDoubleClick = useCallback(
    (node: ForceGraphNode) => {
      // Re-center graph on double-clicked node
      handleEntitySelect(node.entity_type, node.id);
    },
    [handleEntitySelect]
  );

  const handleViewDetails = useCallback(() => {
    if (!selectedNode) return;
    const { entity_type, id } = selectedNode;
    if (entity_type === 'observable') {
      navigate(`/observables/${id}`);
    } else if (entity_type === 'threat_actor') {
      navigate(`/threat-actors/${id}`);
    } else if (entity_type === 'campaign') {
      navigate(`/campaigns/${id}`);
    } else if (entity_type === 'technique') {
      navigate(`/attack`);
    }
  }, [selectedNode, navigate]);

  const nodeCanvasObject = useCallback(
    (
      node: ForceGraphNode,
      ctx: CanvasRenderingContext2D,
      globalScale: number
    ) => {
      const nodeSize = 6 + (linkCountMap[node.id] || 0) * 1.5;
      const fontSize = Math.max(10 / globalScale, 2);
      const isSelected = selectedNode?.id === node.id;
      const isCenter = node.id === entityId;

      const x = node.x ?? 0;
      const y = node.y ?? 0;

      // Draw highlight ring for selected or center node
      if (isSelected || isCenter) {
        ctx.beginPath();
        ctx.arc(x, y, nodeSize + 3, 0, 2 * Math.PI);
        ctx.strokeStyle = isSelected ? '#ffffff' : '#3b82f6';
        ctx.lineWidth = isCenter ? 2 / globalScale : 1.5 / globalScale;
        if (isCenter && !isSelected) {
          ctx.setLineDash([4 / globalScale, 2 / globalScale]);
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, nodeSize, 0, 2 * Math.PI);
      ctx.fillStyle = node.color + '40'; // semi-transparent fill
      ctx.fill();
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 1.5 / globalScale;
      ctx.stroke();

      // Draw label
      ctx.font = `${fontSize}px monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#d1d5db';

      // Truncate label for display
      const maxLen = 20;
      const displayLabel =
        node.label.length > maxLen
          ? node.label.slice(0, maxLen) + '...'
          : node.label;
      ctx.fillText(displayLabel, x, y + nodeSize + 2);
    },
    [linkCountMap, selectedNode, entityId]
  );

  const nodePointerAreaPaint = useCallback(
    (node: ForceGraphNode, color: string, ctx: CanvasRenderingContext2D) => {
      const nodeSize = 6 + (linkCountMap[node.id] || 0) * 1.5;
      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, nodeSize + 4, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
    },
    [linkCountMap]
  );

  const linkCanvasObject = useCallback(
    (
      link: ForceGraphLink,
      ctx: CanvasRenderingContext2D,
      globalScale: number
    ) => {
      const source = link.source as ForceGraphNode;
      const target = link.target as ForceGraphNode;
      if (!source.x || !target.x) return;

      const sx = source.x;
      const sy = source.y ?? 0;
      const tx = target.x;
      const ty = target.y ?? 0;

      // Draw link line
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.strokeStyle = '#6b728080';
      ctx.lineWidth = 1 / globalScale;
      ctx.stroke();

      // Draw link label at midpoint
      const fontSize = Math.max(8 / globalScale, 1.5);
      if (fontSize > 2) {
        const mx = (sx + tx) / 2;
        const my = (sy + ty) / 2;

        ctx.font = `${fontSize}px monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#9ca3af';
        ctx.fillText(link.label, mx, my - fontSize * 0.6);
      }
    },
    []
  );

  // Collect unique entity types present in graph for the legend
  const legendItems = useMemo(() => {
    if (!data) return [];

    const typeSet = new Map<string, string>();
    for (const node of data.nodes) {
      if (node.entity_type === 'observable') {
        const obsType = node.metadata?.observable_type as string;
        if (obsType && !typeSet.has(`obs:${obsType}`)) {
          typeSet.set(`obs:${obsType}`, OBSERVABLE_TYPE_COLORS[obsType] || '#3b82f6');
        }
      } else if (!typeSet.has(node.entity_type)) {
        typeSet.set(
          node.entity_type,
          ENTITY_TYPE_COLORS[node.entity_type] || '#9ca3af'
        );
      }
    }

    return Array.from(typeSet.entries()).map(([key, color]) => {
      const label = key.startsWith('obs:')
        ? key.replace('obs:', '')
        : ENTITY_TYPE_LABELS[key] || key;
      return { label, color };
    });
  }, [data]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Graph Explorer</h1>
        <p className="text-muted-foreground">
          Visualize relationships between observables, threat actors, campaigns,
          and techniques
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        {/* Search */}
        <div className="flex-1">
          <label className="text-sm font-medium mb-1 block">
            Search Entity
          </label>
          <SearchBar onSelect={handleEntitySelect} />
        </div>

        {/* Depth selector */}
        <div>
          <label className="text-sm font-medium mb-1 block">Depth</label>
          <div className="flex gap-1">
            {[1, 2, 3].map((d) => (
              <Button
                key={d}
                size="sm"
                variant={depth === d ? 'default' : 'outline'}
                onClick={() => setDepth(d)}
                className="w-10"
              >
                {d}
              </Button>
            ))}
          </div>
        </div>

        {/* Filter toggles */}
        <div className="flex gap-2 flex-wrap">
          <Button
            size="sm"
            variant={filters.includeThreatActors ? 'default' : 'outline'}
            onClick={() =>
              setFilters((f) => ({
                ...f,
                includeThreatActors: !f.includeThreatActors,
              }))
            }
            className={cn(
              filters.includeThreatActors && 'bg-red-600 hover:bg-red-700'
            )}
          >
            Threat Actors
          </Button>
          <Button
            size="sm"
            variant={filters.includeCampaigns ? 'default' : 'outline'}
            onClick={() =>
              setFilters((f) => ({
                ...f,
                includeCampaigns: !f.includeCampaigns,
              }))
            }
            className={cn(
              filters.includeCampaigns && 'bg-orange-600 hover:bg-orange-700'
            )}
          >
            Campaigns
          </Button>
          <Button
            size="sm"
            variant={filters.includeTechniques ? 'default' : 'outline'}
            onClick={() =>
              setFilters((f) => ({
                ...f,
                includeTechniques: !f.includeTechniques,
              }))
            }
            className={cn(
              filters.includeTechniques && 'bg-purple-600 hover:bg-purple-700'
            )}
          >
            Techniques
          </Button>
        </div>
      </div>

      {/* Graph area */}
      <Card>
        <CardContent className="p-0 relative overflow-hidden">
          {!entityId ? (
            <div className="flex items-center justify-center py-32 text-muted-foreground">
              <div className="text-center space-y-2">
                <p className="text-lg font-medium">No entity selected</p>
                <p className="text-sm">
                  Use the search bar above to find an observable, threat actor,
                  or campaign to explore.
                </p>
              </div>
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-32">
              <LoadingSpinner size="lg" />
            </div>
          ) : isError ? (
            <div className="flex items-center justify-center py-32 text-red-400">
              <p>Failed to load graph data. Please try again.</p>
            </div>
          ) : graphData.nodes.length === 0 ? (
            <div className="flex items-center justify-center py-32 text-muted-foreground">
              <p>No connections found for this entity.</p>
            </div>
          ) : (
            <>
              <div className="bg-muted/20" style={{ height: '560px' }}>
                <ForceGraph2D
                  ref={graphRef}
                  graphData={graphData}
                  nodeCanvasObject={nodeCanvasObject}
                  nodePointerAreaPaint={nodePointerAreaPaint}
                  linkCanvasObject={linkCanvasObject}
                  onNodeClick={handleNodeClick}
                  onNodeDragEnd={(node: ForceGraphNode) => {
                    node.x = node.x;
                    node.y = node.y;
                  }}
                  onNodeRightClick={handleNodeDoubleClick}
                  cooldownTicks={100}
                  d3AlphaDecay={0.03}
                  d3VelocityDecay={0.3}
                  backgroundColor="transparent"
                  width={undefined}
                  height={560}
                  enableZoomInteraction={true}
                  enablePanInteraction={true}
                />
              </div>

              {/* Legend */}
              {legendItems.length > 0 && (
                <div className="flex flex-wrap gap-3 p-3 border-t border-border">
                  {legendItems.map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center gap-1.5"
                    >
                      <div
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="text-xs text-muted-foreground">
                        {item.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Stats */}
              <div className="flex items-center gap-4 px-3 pb-3 text-xs text-muted-foreground">
                <span>{graphData.nodes.length} nodes</span>
                <span>{graphData.links.length} edges</span>
                <span className="ml-auto">
                  Right-click a node to re-center the graph on it
                </span>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Detail Panel */}
      {selectedNode && (
        <DetailPanel node={selectedNode} onViewDetails={handleViewDetails} />
      )}
    </div>
  );
}

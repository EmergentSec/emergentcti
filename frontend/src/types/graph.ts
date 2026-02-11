export interface GraphNode {
  id: string;
  entity_type: 'observable' | 'threat_actor' | 'campaign' | 'technique';
  label: string;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship_type: string;
  metadata: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

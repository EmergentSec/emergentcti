export type RelationshipType =
  | 'resolves-to'
  | 'contains'
  | 'communicates-with'
  | 'drops'
  | 'downloads'
  | 'associated-with'
  | 'belongs-to'
  | 'hosts'
  | 'delivers'
  | 'indicates'
  | 'related-to';

export const RELATIONSHIP_TYPES: RelationshipType[] = [
  'resolves-to',
  'contains',
  'communicates-with',
  'drops',
  'downloads',
  'associated-with',
  'belongs-to',
  'hosts',
  'delivers',
  'indicates',
  'related-to',
];

export interface ObservableSummary {
  id: string;
  type: string;
  value: string;
  confidence_score: number;
}

export interface RelationshipCreate {
  target_id: string;
  relationship_type: RelationshipType;
  confidence?: number;
  metadata?: Record<string, unknown> | null;
}

export interface RelationshipUpdate {
  relationship_type?: RelationshipType;
  confidence?: number;
  metadata?: Record<string, unknown> | null;
}

export interface RelationshipResponse {
  id: string;
  source_id: string;
  target_id: string;
  relationship_type: string;
  confidence: number;
  metadata: Record<string, unknown> | null;
  created_at: string;
  created_by: string | null;
  source: ObservableSummary | null;
  target: ObservableSummary | null;
}

export interface GraphNode {
  id: string;
  type: string;
  value: string;
  confidence_score: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

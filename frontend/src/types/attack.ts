export interface TacticResponse {
  id: string;
  external_id: string;
  name: string;
  description: string | null;
  url: string | null;
  short_name: string;
  order: number;
}

export interface TechniqueResponse {
  id: string;
  external_id: string;
  name: string;
  description: string | null;
  is_subtechnique: boolean;
  parent_id: string | null;
  url: string | null;
  tactic_ids: string[];
}

export interface HeatmapCell {
  technique_id: string;
  technique_external_id: string;
  technique_name: string;
  tactic_id: string;
  count: number;
}

export interface HeatmapResponse {
  tactics: TacticResponse[];
  cells: HeatmapCell[];
}

export interface ObservableTechniqueResponse {
  id: string;
  observable_id: string;
  technique_id: string;
  technique_external_id: string;
  technique_name: string;
  added_by: string | null;
  created_at: string;
}

export interface CorrelationRuleCreate {
  name: string;
  enabled?: boolean;
  match_type?: string;
  match_value_pattern?: string;
  match_tags?: string[];
  match_tlp?: string;
  match_confidence_min?: number;
  match_feed_id?: string;
  action_type: 'link_threat_actor' | 'link_campaign' | 'map_technique';
  target_threat_actor_id?: string;
  target_campaign_id?: string;
  target_technique_id?: string;
}

export interface CorrelationRuleUpdate extends Partial<CorrelationRuleCreate> {}

export interface CorrelationRuleResponse {
  id: string;
  name: string;
  enabled: boolean;
  created_by: string | null;
  match_type: string | null;
  match_value_pattern: string | null;
  match_tags: string[] | null;
  match_tlp: string | null;
  match_confidence_min: number | null;
  match_feed_id: string | null;
  action_type: string;
  target_threat_actor_id: string | null;
  target_campaign_id: string | null;
  target_technique_id: string | null;
  target_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface CorrelationEventResponse {
  id: string;
  rule_id: string | null;
  observable_id: string;
  action_type: string;
  target_id: string;
  correlated_at: string;
  source: string;
  rule_name: string | null;
  observable_value: string | null;
  target_name: string | null;
}

export interface CorrelationEventListResponse {
  items: CorrelationEventResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

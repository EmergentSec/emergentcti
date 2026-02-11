export interface AlertRuleCreate {
  name: string;
  enabled?: boolean;
  match_type?: string;
  match_value_pattern?: string;
  match_tags?: string[];
  match_tlp?: string;
  match_confidence_min?: number;
  match_feed_id?: string;
  notification_channels?: Array<{ type: string; webhook_id?: string }>;
  cooldown_minutes?: number;
}

export interface AlertRuleUpdate extends Partial<AlertRuleCreate> {}

export interface AlertRuleResponse {
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
  notification_channels: Array<{ type: string; webhook_id?: string }>;
  cooldown_minutes: number;
  last_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertEventResponse {
  id: string;
  rule_id: string;
  rule_name: string | null;
  observable_id: string;
  observable_value: string | null;
  triggered_at: string;
  notification_sent: boolean;
  notification_error: string | null;
}

export interface AlertEventListResponse {
  items: AlertEventResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface WebhookConfigCreate {
  name: string;
  url: string;
  secret?: string;
  enabled?: boolean;
  events?: string[];
}

export interface WebhookConfigUpdate extends Partial<WebhookConfigCreate> {}

export interface WebhookConfigResponse {
  id: string;
  name: string;
  url: string;
  has_secret: boolean;
  enabled: boolean;
  events: string[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebhookTestResponse {
  success: boolean;
  status_code: number | null;
  error: string | null;
}

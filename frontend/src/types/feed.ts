export type FeedType = 'api' | 'taxii' | 'file' | 'scraper';
export type AuthType = 'none' | 'bearer' | 'api_key' | 'basic';

export interface FeedResponse {
  id: string;
  name: string;
  description: string | null;
  feed_type: FeedType;
  url: string | null;
  enabled: boolean;
  schedule_cron: string | null;
  config: Record<string, unknown> | null;
  default_ttl_days: number | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedCreateRequest {
  name: string;
  description?: string;
  feed_type: FeedType;
  url: string;
  enabled?: boolean;
  schedule_cron?: string;
  config?: Record<string, unknown>;
  auth_config?: Record<string, unknown> | null;
  default_ttl_days?: number | null;
}

export interface FeedUpdateRequest {
  name?: string;
  description?: string;
  url?: string;
  enabled?: boolean;
  schedule_cron?: string;
  config?: Record<string, unknown>;
  auth_config?: Record<string, unknown> | null;
  default_ttl_days?: number | null;
}

export interface FeedRunResponse {
  id: string;
  feed_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at: string | null;
  observables_ingested: number;
  error_message: string | null;
}

export interface FeedTriggerResponse {
  status: string;
  feed_id: string;
}

export interface ProviderInfo {
  name: string;
  supported_types: string[];
  configured: boolean;
  enabled: boolean;
}

export interface EnrichmentConfigResponse {
  id: string;
  provider_name: string;
  enabled: boolean;
  auto_enrich: boolean;
  has_api_key: boolean;
  config: Record<string, unknown>;
  priority: number;
  supported_types: string[];
  created_at: string;
  updated_at: string;
}

export interface EnrichmentConfigUpdate {
  enabled?: boolean;
  auto_enrich?: boolean;
  api_key?: string;
  config?: Record<string, unknown>;
  priority?: number;
}

export interface EnrichmentRunResponse {
  id: string;
  observable_id: string;
  provider_name: string;
  status: 'pending' | 'running' | 'success' | 'failure';
  result_data: Record<string, unknown> | null;
  summary: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  triggered_by: string | null;
  created_at: string;
}

export interface EnrichmentTriggerRequest {
  provider_name?: string;
}

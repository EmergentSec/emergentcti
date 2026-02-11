export type CampaignStatus = 'active' | 'historical' | 'suspected';

export interface CampaignObservable {
  id: string;
  type: string;
  value: string;
}

export interface CampaignThreatActor {
  id: string;
  name: string;
}

export interface CampaignResponse {
  id: string;
  name: string;
  description: string | null;
  threat_actor_id: string | null;
  threat_actor: CampaignThreatActor | null;
  status: string;
  first_seen: string | null;
  last_seen: string | null;
  tlp: string;
  objective: string | null;
  external_references: Array<{ source: string; url: string; description?: string }> | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  observables: CampaignObservable[];
}

export interface CampaignCreateRequest {
  name: string;
  description?: string;
  threat_actor_id?: string;
  status?: string;
  first_seen?: string;
  last_seen?: string;
  tlp?: string;
  objective?: string;
  external_references?: Array<{ source: string; url: string; description?: string }>;
}

export interface CampaignUpdateRequest {
  name?: string;
  description?: string;
  threat_actor_id?: string | null;
  status?: string;
  first_seen?: string;
  last_seen?: string;
  tlp?: string;
  objective?: string;
  external_references?: Array<{ source: string; url: string; description?: string }>;
}

export interface CampaignFilters {
  page?: number;
  size?: number;
  name?: string;
  status?: CampaignStatus | '';
  threat_actor_id?: string;
}

export interface TimelineEvent {
  timestamp: string;
  event_type: string;
  description: string;
  observable_id: string | null;
  observable_value: string | null;
  observable_type: string | null;
}

export interface CampaignTimelineResponse {
  campaign_id: string;
  campaign_name: string;
  events: TimelineEvent[];
}

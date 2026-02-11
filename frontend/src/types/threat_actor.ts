export interface ThreatActorObservable {
  id: string;
  type: string;
  value: string;
}

export interface ThreatActorTechnique {
  id: string;
  external_id: string;
  name: string;
}

export interface ThreatActorResponse {
  id: string;
  name: string;
  aliases: string[] | null;
  description: string | null;
  motivation: string | null;
  sophistication: string | null;
  country: string | null;
  first_seen: string | null;
  last_seen: string | null;
  tlp: string;
  external_references: Array<{ source: string; url: string; description?: string }> | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  observables: ThreatActorObservable[];
  techniques: ThreatActorTechnique[];
}

export interface ThreatActorCreateRequest {
  name: string;
  aliases?: string[];
  description?: string;
  motivation?: string;
  sophistication?: string;
  country?: string;
  first_seen?: string;
  last_seen?: string;
  tlp?: string;
  external_references?: Array<{ source: string; url: string; description?: string }>;
}

export interface ThreatActorUpdateRequest {
  name?: string;
  aliases?: string[];
  description?: string;
  motivation?: string;
  sophistication?: string;
  country?: string;
  first_seen?: string;
  last_seen?: string;
  tlp?: string;
  external_references?: Array<{ source: string; url: string; description?: string }>;
}

export interface ThreatActorFilters {
  page?: number;
  size?: number;
  name?: string;
  country?: string;
  motivation?: string;
}

export interface ThreatActorCampaign {
  id: string;
  name: string;
  status: string;
  first_seen: string | null;
  last_seen: string | null;
}

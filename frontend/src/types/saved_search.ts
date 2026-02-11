export interface SavedSearchFilters {
  type?: string | null;
  value?: string | null;
  confidence_min?: number | null;
  tlp?: string | null;
  feed_id?: string | null;
  category?: string | null;
  tag?: string | null;
}

export interface SavedSearchCreate {
  name: string;
  filters: SavedSearchFilters;
  is_shared?: boolean;
}

export interface SavedSearchUpdate {
  name?: string | null;
  filters?: SavedSearchFilters | null;
  is_shared?: boolean | null;
}

export interface SavedSearchOwner {
  id: string;
  username: string;
}

export interface SavedSearchResponse {
  id: string;
  name: string;
  filters: SavedSearchFilters;
  is_default: boolean;
  is_shared: boolean;
  user_id: string;
  user: SavedSearchOwner | null;
  created_at: string;
  updated_at: string;
}

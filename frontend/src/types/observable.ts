export type ObservableType =
  | 'ip-addr'
  | 'domain-name'
  | 'url'
  | 'file-hash'
  | 'email-addr'
  | 'command-line'

export interface ObservableSource {
  feed_id: string
  feed_name: string
  source_confidence: number
  native_confidence: number
  first_seen_by_feed: string
  last_seen_by_feed: string
}

export interface Observable {
  id: string
  type: ObservableType
  value: string
  confidence_score: number
  first_seen: string | null
  last_seen: string | null
  source_count: number
  sources: ObservableSource[]
  /** Derived at read time from the current allowlist; allowlisted observables are excluded from exports. */
  allowlisted: boolean
  allowlist_entry_ids: string[]
  created_at: string
  updated_at: string
}

export interface ObservableListResponse {
  items: Observable[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ObservableFilters {
  q?: string
  type?: ObservableType | ''
  confidence_min?: number
  source?: string
  feed_id?: string
  last_seen_after?: string
  page?: number
  size?: number
  sort?: string
  order?: 'asc' | 'desc'
}

export interface ObservableCreate {
  type: ObservableType
  value: string
  confidence_score: number
}

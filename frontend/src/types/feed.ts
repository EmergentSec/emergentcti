export type FeedType = 'api' | 'file' | 'scraper'
export type FeedRunStatus = 'running' | 'success' | 'failure'

export interface FeedRun {
  id: string
  started_at: string
  completed_at: string | null
  status: FeedRunStatus
  observables_ingested: number
  observables_new: number
  error_message: string | null
}

export interface Feed {
  id: string
  name: string
  description: string | null
  feed_type: FeedType
  url: string | null
  config: Record<string, unknown> | null
  schedule_cron: string | null
  enabled: boolean
  is_preconfigured: boolean
  default_confidence: number
  last_run_at: string | null
  observable_count: number
  latest_run: FeedRun | null
  created_at: string
  updated_at: string
}

export interface FeedCreate {
  name: string
  description?: string
  feed_type: FeedType
  url?: string
  config?: Record<string, unknown>
  schedule_cron?: string
  enabled?: boolean
  auth_config?: Record<string, unknown>
  default_confidence?: number
}

export interface FeedUpdate {
  name?: string
  description?: string
  feed_type?: FeedType
  url?: string
  config?: Record<string, unknown>
  schedule_cron?: string
  enabled?: boolean
  auth_config?: Record<string, unknown>
  default_confidence?: number
}

export interface FeedHealth {
  id: string
  name: string
  enabled: boolean
  last_run_status: 'running' | 'success' | 'failure' | null
  last_run_at: string | null
  observable_count: number
}

export interface DashboardStats {
  total_observables: number
  by_type: Record<string, number>
  total_feeds: number
  feeds_enabled: number
  last_24h_ingested: number
  feeds_health: FeedHealth[]
  confidence_distribution: { critical: number; high: number; medium: number; low: number }
  feed_errors_24h: number
  daily_ingest_14d: { date: string; count: number }[]
}

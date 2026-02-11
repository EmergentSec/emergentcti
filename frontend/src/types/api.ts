export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface ErroredFeed {
  feed_id: string;
  feed_name: string;
  error_message: string | null;
  last_run_at: string | null;
}

export interface DashboardStats {
  total_observables: number;
  total_feeds: number;
  active_feeds: number;
  feeds_with_errors: number;
  observables_today: number;
  observables_by_type: Record<string, number>;
  recent_observables: RecentObservable[];
  recent_feed_runs: FeedRunSummary[];
  errored_feeds: ErroredFeed[];
}

export interface RecentObservable {
  id: string;
  type: string;
  value: string;
  confidence_score: number;
  created_at: string;
}

export interface FeedRunSummary {
  feed_id: string;
  feed_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  observables_created: number;
  observables_updated: number;
  errors: number;
}

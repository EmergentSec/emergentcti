export type ReportOrigin = 'provider' | 'internal'
export type ContentFormat = 'markdown' | 'text'

export interface ReportAttachment {
  id: string
  original_filename: string
  content_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export interface ReportSummary {
  id: string
  title: string
  origin: ReportOrigin
  source_name: string | null
  published_at: string | null
  summary: string | null
  is_ai_generated: boolean
  ai_provider: string | null
  ai_model: string | null
  has_attachment: boolean
  created_at: string
  updated_at: string
}

export interface LinkedObservable {
  id: string
  type: string
  value: string
  confidence_score: number
}

export interface ReportDetail extends ReportSummary {
  source_url: string | null
  content: string | null
  content_format: ContentFormat
  ai_generated_at: string | null
  created_by: string | null
  attachment: ReportAttachment | null
  observables: LinkedObservable[]
}

export interface ReportListResponse {
  items: ReportSummary[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ReportCreate {
  title: string
  origin: ReportOrigin
  source_name?: string | null
  published_at?: string | null
  summary?: string | null
  source_url?: string | null
  content?: string | null
  content_format?: ContentFormat
  is_ai_generated?: boolean
  ai_provider?: string | null
  ai_model?: string | null
  ai_generated_at?: string | null
}

export type ReportUpdate = Partial<ReportCreate>

export interface ReportFilters {
  q?: string
  origin?: ReportOrigin
  source_name?: string
  published_from?: string
  published_to?: string
  ai_generated?: boolean
  page?: number
  size?: number
}

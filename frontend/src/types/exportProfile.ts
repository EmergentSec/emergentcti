import type { ObservableType } from './observable'

export type ExportProfileFormat = 'text' | 'json'

export interface ExportProfile {
  id: string
  name: string
  description: string | null
  format: ExportProfileFormat
  type: ObservableType | null
  confidence_min: number
  max_age_days: number | null
  feed_id: string | null
  created_at: string
  updated_at: string
}

export interface ExportProfileInput {
  name: string
  description: string | null
  format: ExportProfileFormat
  type: ObservableType | null
  confidence_min: number
  max_age_days: number | null
  feed_id: string | null
}

export interface ExportProfilePreview {
  count: number
  excluded_allowlisted: number
  sample: string[]
}

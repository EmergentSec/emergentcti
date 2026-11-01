import type { ObservableType } from './observable'
import type { ExcludedByTlpCounts, ExportDestination } from './tlp'

export type { ExportDestination, ExcludedByTlpCounts } from './tlp'

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
  destination: ExportDestination
  tags: string[]
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
  destination: ExportDestination
  tags: string[]
}

export interface ExportProfilePreview {
  count: number
  excluded_allowlisted: number
  excluded_by_tlp: ExcludedByTlpCounts
  sample: string[]
}

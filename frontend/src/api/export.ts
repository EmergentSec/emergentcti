/**
 * Build relative export URLs for use as <a href download> targets.
 * These are NOT axios calls — the browser navigates and downloads directly
 * using the JWT cookie that the browser sends automatically on navigation.
 */

import type { ObservableType } from '@/types/observable'

export type BlocklistObsType = 'ip-addr' | 'domain-name' | 'url'

export interface ExportFilters {
  /** Optional observable type filter (adds `?type=` param when set). */
  type?: ObservableType
  confidence_min?: number
  /** Feed UUID, 'manual', or undefined/empty (all sources). */
  source?: string
}

/**
 * Builds a blocklist URL for a given observable type.
 *
 * - `source === 'manual'` or empty → feed_id param omitted
 * - `confidence_min === 0` or undefined → param omitted
 */
export function blocklistUrl(obsType: BlocklistObsType, filters: ExportFilters): string {
  const params = new URLSearchParams()
  if (filters.confidence_min != null && filters.confidence_min > 0) {
    params.set('confidence_min', String(filters.confidence_min))
  }
  if (filters.source && filters.source !== 'manual') {
    params.set('feed_id', filters.source)
  }
  const qs = params.toString()
  return `/api/v1/export/blocklist/${obsType}${qs ? `?${qs}` : ''}`
}

/**
 * Builds a full JSON export URL with the current filters applied.
 *
 * - `source === 'manual'` or empty → feed_id param omitted
 * - `confidence_min === 0` or undefined → param omitted
 */
export function jsonExportUrl(filters: ExportFilters): string {
  const params = new URLSearchParams()
  if (filters.type) {
    params.set('type', filters.type)
  }
  if (filters.confidence_min != null && filters.confidence_min > 0) {
    params.set('confidence_min', String(filters.confidence_min))
  }
  if (filters.source && filters.source !== 'manual') {
    params.set('feed_id', filters.source)
  }
  const qs = params.toString()
  return `/api/v1/export/json${qs ? `?${qs}` : ''}`
}

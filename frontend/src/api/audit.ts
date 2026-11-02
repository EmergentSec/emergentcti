import api from './client'

export type AuditActorType = 'user' | 'api_key' | 'system'

export type AuditOutcome =
  | 'succeeded'
  | 'failed'
  | 'denied'
  | 'initiated'
  | 'completed'
  | 'interrupted'

export interface AuditEvent {
  id: string
  occurred_at: string
  actor_type: AuditActorType
  actor_id: string | null
  actor_label: string | null
  action: string
  resource_type: string
  resource_id: string | null
  resource_label: string | null
  outcome: AuditOutcome
  summary: Record<string, unknown>
}

export interface AuditEventsResponse {
  items: AuditEvent[]
  total: number
  page: number
  size: number
  pages: number
}

export interface AuditMeta {
  actions: string[]
  actor_types: string[]
  outcomes: string[]
  resource_types: string[]
  retention_days: number
}

export interface AuditEventFilters {
  since?: string
  until?: string
  actor_type?: string
  actor_id?: string
  action?: string | string[]
  resource_type?: string
  resource_id?: string
  outcome?: string | string[]
  page?: number
  size?: number
}

const REPEATABLE_KEYS = new Set(['action', 'outcome'])

/** Build query params for GET /audit/events (repeatable action and outcome). */
export function buildAuditParams(
  params: AuditEventFilters,
): Record<string, unknown> | URLSearchParams {
  const flat: Record<string, unknown> = {}
  const repeated: [string, string][] = []

  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === '' || val === null) continue
    if (REPEATABLE_KEYS.has(key)) {
      const arr = Array.isArray(val) ? val : [val]
      for (const item of arr) {
        if (item !== undefined && item !== '' && item !== null) {
          repeated.push([key, String(item)])
        }
      }
      continue
    }
    flat[key] = val
  }

  if (repeated.length === 0) return flat

  const search = new URLSearchParams()
  for (const [key, val] of Object.entries(flat)) {
    search.append(key, String(val))
  }
  for (const [key, val] of repeated) {
    search.append(key, val)
  }
  return search
}

export async function getAuditEvents(
  filters: AuditEventFilters = {},
): Promise<AuditEventsResponse> {
  const { data } = await api.get<AuditEventsResponse>('/audit/events', {
    params: buildAuditParams(filters),
  })
  return data
}

export async function getAuditMeta(): Promise<AuditMeta> {
  const { data } = await api.get<AuditMeta>('/audit/meta')
  return data
}

export function auditOutcomeLabel(outcome: AuditOutcome): string {
  return outcome
}

export type AuditOutcomeBadgeVariant =
  | 'success'
  | 'destructive'
  | 'warning'
  | 'secondary'
  | 'default'

export function auditOutcomeBadgeVariant(outcome: AuditOutcome): AuditOutcomeBadgeVariant {
  switch (outcome) {
    case 'succeeded':
    case 'completed':
      return 'success'
    case 'failed':
    case 'interrupted':
      return 'destructive'
    case 'denied':
      return 'warning'
    case 'initiated':
      return 'secondary'
    default:
      return 'default'
  }
}

/** Flatten summary for display; nested values are JSON-stringified. */
export function formatAuditSummaryEntries(
  summary: Record<string, unknown>,
): { key: string; value: string }[] {
  return Object.entries(summary).map(([key, val]) => ({
    key,
    value:
      val !== null && typeof val === 'object'
        ? JSON.stringify(val)
        : String(val ?? ''),
  }))
}

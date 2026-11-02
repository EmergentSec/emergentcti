/** User-facing label for missing numeric or monetary API values (never show 0 as a stand-in). */
export function displayUnknown(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return 'Unknown'
  if (typeof value === 'string' && value.trim() === '') return 'Unknown'
  return String(value)
}

export function displayUsdEstimate(value: string | null | undefined): string {
  if (value === null || value === undefined) return 'Unknown'
  return `$${value} est.`
}

export function displayTokenCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'Unknown'
  return String(value)
}

export function displayUsageSource(source: 'provider_reported' | 'unknown' | null | undefined): string {
  if (source === 'provider_reported') return 'provider-reported'
  return 'Unknown'
}

/** `YYYY-MM` for the current UTC calendar month. */
export function currentUtcMonth(): string {
  const now = new Date()
  const y = now.getUTCFullYear()
  const m = String(now.getUTCMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

/** Long label for a UTC month picker value, e.g. "November 2026". */
export function formatUtcMonthLabel(month: string): string {
  const [y, m] = month.split('-').map(Number)
  if (!y || !m) return month
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' })
}

export function inferenceTestBlockReason(decision: string): string | null {
  switch (decision) {
    case 'blocked_unpriced':
      return 'This model has no local pricing row and your policy blocks unpriced models.'
    case 'over_budget':
      return 'Sending this test would exceed the configured monthly budget estimate.'
    case 'allowed':
      return null
    default:
      return 'This request is blocked by local guardrails.'
  }
}

function isZeroDecimal(value: string): boolean {
  return /^0*(\.0*)?$/.test(value.trim())
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/**
 * Cost for a usage aggregate. `estimated_cost_usd` sums known costs only, so
 * whenever some costs are unknown that must be said: never a bare "$0".
 */
export function displayCostWithUnknown(totals: { estimated_cost_usd: string; cost_unknown_requests: number }): string {
  const unknown = totals.cost_unknown_requests
  if (unknown <= 0) return displayUsdEstimate(totals.estimated_cost_usd)
  if (isZeroDecimal(totals.estimated_cost_usd)) return `Unknown (${plural(unknown, 'request')})`
  return `${displayUsdEstimate(totals.estimated_cost_usd)} + ${unknown} unknown`
}

/** Known token count for an aggregate, flagged when some requests' counts are unknown. */
export function displayTokensWithUnknown(known: number, unknownRequests: number): string {
  if (unknownRequests <= 0) return String(known)
  if (known === 0) return `Unknown (${plural(unknownRequests, 'request')})`
  return `${known} + ${unknownRequests} unknown`
}

/** Absolute value of a decimal string without going through a float. */
export function absDecimal(value: string): string {
  return value.trim().replace(/^-/, '')
}

const MONTH_RE = /^(\d{4})-(0[1-9]|1[0-2])$/

/** True for a `YYYY-MM` the backend's `parse_month` accepts (year 2000 or later). */
export function isValidUsageMonth(value: string): boolean {
  const m = MONTH_RE.exec(value)
  return !!m && Number(m[1]) >= 2000
}

/** `2026-11-02 14:05 UTC` from an ISO timestamp; the raw value if it can't be parsed. */
export function formatUtcTimestamp(iso: string): string {
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  return `${new Date(t).toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

const ACTION_LABELS: Record<string, string> = {
  inference_test: 'connection inference tests',
}

/** "In scope: …" copy built from the report's `actions_in_scope`. */
export function describeActionsInScope(actions: readonly string[]): string {
  if (actions.length === 0) return 'In scope: no actions.'
  return `In scope: ${actions.map((a) => ACTION_LABELS[a] ?? a).join(', ')}.`
}

/** Cost cell for one usage record: reserved holds, non-billed and unknown are distinct. */
export function displayRecordCost(rec: {
  status: string
  billable: string
  reserved_usd: string | null
  cost_usd: string | null
}): string {
  if (rec.cost_usd !== null) return displayUsdEstimate(rec.cost_usd)
  if (rec.status === 'reserved' && rec.reserved_usd !== null) return `Reserved ${displayUsdEstimate(rec.reserved_usd)}`
  if (rec.billable === 'no') return 'Not billed'
  return 'Unknown'
}

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

import { isAxiosError } from 'axios'

/** HTTP status of a failed API call, or undefined for non-HTTP errors. */
export function apiErrorStatus(err: unknown): number | undefined {
  return isAxiosError(err) ? err.response?.status : undefined
}

/** Prefer the API's `detail` string, then FastAPI validation messages, then the fallback. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail) return detail
    // FastAPI validation errors: [{ msg, ... }]
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg
  }
  return fallback
}

export type ImportValidationHighlight = { type: string; value: string }

/** Parsed 422 import validation detail (pinned FastAPI list shape + string fallback). */
export function importValidationErrorDetail(err: unknown): {
  messages: string[]
  highlightedItems: ImportValidationHighlight[]
} | null {
  if (!isAxiosError(err) || err.response?.status !== 422) return null
  const detail = err.response?.data?.detail
  if (typeof detail === 'string' && detail) {
    return { messages: [detail], highlightedItems: [] }
  }
  if (!Array.isArray(detail)) return null

  const messages: string[] = []
  const highlightedItems: ImportValidationHighlight[] = []
  for (const entry of detail) {
    if (entry && typeof entry.msg === 'string') messages.push(entry.msg)
    if (entry?.type === 'not_a_candidate' && Array.isArray(entry.items)) {
      for (const item of entry.items) {
        if (item && typeof item.type === 'string' && typeof item.value === 'string') {
          highlightedItems.push({ type: item.type, value: item.value })
        }
      }
    }
  }
  return messages.length > 0 ? { messages, highlightedItems } : null
}

/** All validation messages for import 422, or fallback via apiErrorMessage. */
export function importValidationErrorMessage(err: unknown, fallback: string): string {
  const parsed = importValidationErrorDetail(err)
  if (parsed) return parsed.messages.join('\n')
  return apiErrorMessage(err, fallback)
}

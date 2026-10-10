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

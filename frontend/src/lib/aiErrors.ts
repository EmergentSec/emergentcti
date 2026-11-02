import { isAxiosError } from 'axios'
import { apiErrorMessage } from './apiError'
import type { AiError, AiErrorCategory } from '@/types/ai'

/**
 * Fixed, user-facing copy per error category. The backend's `message` is
 * deliberately not shown: these strings are the single source of UI wording
 * and can never echo provider output.
 */
export const AI_ERROR_MESSAGES: Record<AiErrorCategory, string> = {
  invalid_credentials:
    "The provider rejected this API key. Check that it was copied in full and hasn't been revoked.",
  permission_denied: "This key isn't allowed to do that. Check the key's permissions or project access with the provider.",
  rate_limited: 'The provider is rate-limiting requests. Wait a minute and try again.',
  insufficient_quota: 'The provider account is out of credit or quota. Check billing with the provider.',
  model_unavailable: "That model isn't available to this key. Pick another model or check the ID.",
  timeout: "The provider didn't respond in time. Try again.",
  network_error: "Couldn't reach the provider from this server. Check its outbound network access.",
  provider_error: 'The provider returned an error. Try again later.',
  not_configured: 'No API key is saved for this provider.',
  budget_exceeded:
    'This request would exceed the configured monthly budget estimate. Raise the budget or wait for the next UTC month.',
  concurrency_limit: 'Too many AI requests are in flight. Wait for one to finish and try again.',
  local_rate_limited: 'Too many AI requests in the last minute. Wait briefly and try again.',
  model_blocked_unpriced:
    'This model has no local pricing row and your policy blocks unpriced models. Add pricing or change the policy.',
  sharing_forbidden: 'One or more items can no longer be shared with an external AI provider under TLP rules.',
  sharing_not_approved:
    'The outbound preview changed or expired. Review the content again before sending.',
}

const GENERIC = 'Something went wrong talking to the provider.'

export function describeAiCategory(category: string | null | undefined): string {
  if (category && category in AI_ERROR_MESSAGES) return AI_ERROR_MESSAGES[category as AiErrorCategory]
  return GENERIC
}

function asAiError(value: unknown): AiError | null {
  if (value && typeof value === 'object' && typeof (value as AiError).category === 'string') {
    return value as AiError
  }
  return null
}

/** Extracts an `AiError` from a failed request, whether or not it is wrapped in FastAPI's `detail`. */
export function aiErrorFromResponse(err: unknown): AiError | null {
  if (!isAxiosError(err)) return null
  const data = err.response?.data
  return asAiError(data?.detail) ?? asAiError(data)
}

/** User-facing message for a failed AI settings request. Never dumps raw responses. */
export function aiRequestErrorMessage(err: unknown, fallback: string): string {
  const aiErr = aiErrorFromResponse(err)
  if (aiErr) return describeAiCategory(aiErr.category)
  return apiErrorMessage(err, fallback)
}

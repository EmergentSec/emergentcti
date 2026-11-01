// Shared contract: docs/superpowers/specs/2026-11-01-ai-provider-settings.md
// No type here ever carries an API key: keys are write-only.

export type AiProvider = 'anthropic' | 'openai' | 'openrouter' | 'xai'

export const AI_PROVIDERS: readonly AiProvider[] = ['anthropic', 'openai', 'openrouter', 'xai']

export type ModelSource = 'live' | 'cache' | 'fallback'

export type AiErrorCategory =
  | 'invalid_credentials'
  | 'permission_denied'
  | 'rate_limited'
  | 'insufficient_quota'
  | 'model_unavailable'
  | 'timeout'
  | 'network_error'
  | 'provider_error'
  | 'not_configured'

export interface AiModel {
  /** Exact provider model ID. */
  id: string
  /** Friendly name; equals `id` when the provider gives none. */
  name: string
  context_length?: number | null
}

export interface AiError {
  category: AiErrorCategory
  message: string
}

export interface AiProviderStatus {
  provider: AiProvider
  display_name: string
  configured: boolean
  /** Last four characters of the key, e.g. "a1b2"; rendered as "••••a1b2". */
  key_hint: string | null
  models_fetched_at: string | null
  last_check_status: 'ok' | 'error' | null
  last_check_category: AiErrorCategory | null
  last_checked_at: string | null
  /** Provider console URL for creating a key. */
  setup_url: string
}

export interface AiDefault {
  provider: AiProvider
  model: string
  is_custom: boolean
}

export interface AiSettings {
  /** Always all four providers, configured or not, in fixed order. */
  providers: AiProviderStatus[]
  default: AiDefault | null
}

export interface AiModelList {
  provider: AiProvider
  source: ModelSource
  fetched_at: string | null
  models: AiModel[]
  /** Set when a live fetch was attempted and failed. */
  error: AiError | null
}

export interface AiCheckResult {
  ok: boolean
  error: AiError | null
  checked_at: string
}

export interface AiInferenceResult {
  ok: boolean
  error: AiError | null
  latency_ms: number | null
}

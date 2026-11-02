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
  | 'budget_exceeded'
  | 'concurrency_limit'
  | 'local_rate_limited'
  | 'model_blocked_unpriced'
  | 'sharing_forbidden'
  | 'sharing_not_approved'

export type AiUsageSource = 'provider_reported' | 'unknown'
export type AiCostSource = 'estimated' | 'unknown'
export type AiUnpricedModelPolicy = 'block' | 'permit'
export type AiInferencePolicyDecision = 'allowed' | 'blocked_unpriced' | 'over_budget'
export type AiUsageRecordStatus = 'reserved' | 'succeeded' | 'failed' | 'cancelled'
export type AiUsageBillable = 'no' | 'yes' | 'unknown'
export type AiAction = 'inference_test'

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

export interface AiUsageSummary {
  record_id: string
  input_tokens: number | null
  output_tokens: number | null
  usage_source: AiUsageSource
  cost_usd: string | null
  cost_source: AiCostSource
}

export interface AiInferenceResult {
  ok: boolean
  error: AiError | null
  latency_ms: number | null
  usage: AiUsageSummary | null
}

export interface AiInferenceTestPreview {
  provider: AiProvider
  model: string
  action: AiAction
  content: string
  max_output_tokens: number
  pricing_known: boolean
  estimated_max_cost_usd: string | null
  policy_decision: AiInferencePolicyDecision
  destination_note: string
}

export interface UsageTotals {
  requests: number
  succeeded: number
  failed: number
  cancelled: number
  reserved: number
  input_tokens: number
  output_tokens: number
  token_unknown_requests: number
  estimated_cost_usd: string | null
  cost_unknown_requests: number
  committed_usd: string
}

export interface AiUsagePeriod {
  month: string
  start: string
  end: string
  timezone: 'UTC'
}

export interface AiUsageBudget {
  monthly_budget_usd: string | null
  committed_usd: string
  remaining_usd: string | null
}

export interface AiUsageResponse {
  period: AiUsagePeriod
  actions_in_scope: AiAction[]
  guarantee: 'local_estimate_only'
  totals: UsageTotals
  budget: AiUsageBudget
  by_provider_model: ({ provider: AiProvider; model: string } & UsageTotals)[]
  by_day: ({ date: string } & UsageTotals)[]
}

export interface AiUsageRecord {
  id: string
  actor_label: string
  action: AiAction
  provider: AiProvider
  model: string
  status: AiUsageRecordStatus
  billable: AiUsageBillable
  started_at: string
  completed_at: string | null
  latency_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
  usage_source: AiUsageSource
  cost_usd: string | null
  cost_source: AiCostSource
  error_category: AiErrorCategory | null
  stale: boolean
}

export interface AiUsageRecordsResponse {
  items: AiUsageRecord[]
  next_before: string | null
}

export interface AiUsagePolicy {
  monthly_budget_usd: string | null
  max_output_tokens: number
  max_concurrent_requests: number
  max_requests_per_minute: number
  unpriced_model_policy: AiUnpricedModelPolicy
  updated_at: string
  guarantee: 'local_estimate_only'
}

export interface AiModelPricingRow {
  provider: AiProvider
  model: string
  input_usd_per_mtok: string
  output_usd_per_mtok: string
  updated_at: string
}

export interface AiPricingList {
  items: AiModelPricingRow[]
}

export type OutboundRefType = 'report' | 'observable'
export type OutboundExcludedReason = 'tlp_restricted' | 'not_found' | 'not_visible'

export interface OutboundRef {
  type: OutboundRefType
  id: string
}

export interface OutboundPreviewItem {
  type: OutboundRefType
  id: string
  label: string
  tlp: string | null
  included: boolean
  excluded_reason: OutboundExcludedReason | null
  redactions: number
}

export interface OutboundPreview {
  provider: AiProvider
  model: string
  destination_note: string
  items: OutboundPreviewItem[]
  content: string
  content_chars: number
  digest: string
  expires_at: string
}

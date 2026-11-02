/**
 * AI usage fixtures in the exact shapes the backend sends.
 *
 * Field sets, order and nullability are copied from the Pydantic schemas in
 * `src/cti/schemas/ai.py` (AiUsageTotals, AiUsageReport, AiUsageRecordItem,
 * AiUsagePolicyOut, AiModelPricingOut, AiInferencePreview) and
 * `src/cti/schemas/ai_outbound.py` (OutboundPreview). Money is a decimal
 * string: usage sums use 6 dp (`gateway.format_usd`), budgets 4 dp, prices
 * 6 dp. `estimated_cost_usd` is never null: it sums known costs only and is
 * "0.000000" when none are known.
 */
import type {
  AiInferenceTestPreview,
  AiModelPricingRow,
  AiUsageByDay,
  AiUsageByProviderModel,
  AiUsagePolicy,
  AiUsageRecord,
  AiUsageResponse,
  OutboundPreview,
  UsageTotals,
} from '@/types/ai'

/** Field names, in schema order, of each backend model the UI reads. */
export const BACKEND_FIELDS = {
  AiUsageTotals: [
    'requests',
    'succeeded',
    'failed',
    'cancelled',
    'reserved',
    'input_tokens',
    'output_tokens',
    'token_unknown_requests',
    'estimated_cost_usd',
    'cost_unknown_requests',
    'committed_usd',
  ],
  AiUsageReport: ['period', 'actions_in_scope', 'guarantee', 'totals', 'budget', 'by_provider_model', 'by_day'],
  AiUsageRecordItem: [
    'id',
    'actor_label',
    'action',
    'provider',
    'model',
    'status',
    'stale',
    'billable',
    'started_at',
    'completed_at',
    'latency_ms',
    'input_tokens',
    'output_tokens',
    'usage_source',
    'reserved_usd',
    'cost_usd',
    'cost_source',
    'error_category',
    'retry_of',
  ],
  AiUsagePolicyOut: [
    'monthly_budget_usd',
    'max_output_tokens',
    'max_concurrent_requests',
    'max_requests_per_minute',
    'unpriced_model_policy',
    'guarantee',
    'updated_at',
  ],
  AiModelPricingOut: ['provider', 'model', 'input_usd_per_mtok', 'output_usd_per_mtok', 'updated_at'],
  AiInferencePreview: [
    'provider',
    'model',
    'action',
    'content',
    'max_output_tokens',
    'pricing_known',
    'estimated_max_cost_usd',
    'policy_decision',
    'destination_note',
  ],
  OutboundPreview: [
    'provider',
    'model',
    'destination_note',
    'items',
    'content',
    'content_chars',
    'digest',
    'expires_at',
  ],
} as const

export function usageTotals(overrides: Partial<UsageTotals> = {}): UsageTotals {
  return {
    requests: 0,
    succeeded: 0,
    failed: 0,
    cancelled: 0,
    reserved: 0,
    input_tokens: 0,
    output_tokens: 0,
    token_unknown_requests: 0,
    estimated_cost_usd: '0.000000',
    cost_unknown_requests: 0,
    committed_usd: '0.000000',
    ...overrides,
  }
}

export function byProviderModel(
  provider: string,
  model: string,
  overrides: Partial<UsageTotals> = {},
): AiUsageByProviderModel {
  return { ...usageTotals(overrides), provider, model }
}

export function byDay(date: string, overrides: Partial<UsageTotals> = {}): AiUsageByDay {
  return { ...usageTotals(overrides), date }
}

/**
 * One permitted, unpriced, succeeded inference test: provider-reported tokens
 * but no cost. This is what the backend returns for H1's scenario.
 */
export const UNPRICED_TOTALS: Partial<UsageTotals> = {
  requests: 1,
  succeeded: 1,
  input_tokens: 12,
  output_tokens: 1,
  estimated_cost_usd: '0.000000',
  cost_unknown_requests: 1,
  committed_usd: '0.500000',
}

export function usageReport(overrides: Partial<AiUsageResponse> = {}): AiUsageResponse {
  return {
    period: {
      month: '2026-11',
      start: '2026-11-01T00:00:00Z',
      end: '2026-12-01T00:00:00Z',
      timezone: 'UTC',
    },
    actions_in_scope: ['inference_test'],
    guarantee: 'local_estimate_only',
    totals: usageTotals(),
    budget: { monthly_budget_usd: null, committed_usd: '0.000000', remaining_usd: null },
    by_provider_model: [],
    by_day: [],
    ...overrides,
  }
}

export function usageRecord(overrides: Partial<AiUsageRecord> = {}): AiUsageRecord {
  return {
    id: '7b1f2c4e-0000-4000-8000-000000000001',
    actor_label: 'admin',
    action: 'inference_test',
    provider: 'anthropic',
    model: 'claude-alpha-20260101',
    status: 'succeeded',
    stale: false,
    billable: 'yes',
    started_at: '2026-11-02T14:05:09.123456Z',
    completed_at: '2026-11-02T14:05:09.900000Z',
    latency_ms: 777,
    input_tokens: 12,
    output_tokens: 1,
    usage_source: 'provider_reported',
    reserved_usd: null,
    cost_usd: '0.000051',
    cost_source: 'estimated',
    error_category: null,
    retry_of: null,
    ...overrides,
  }
}

export function usagePolicy(overrides: Partial<AiUsagePolicy> = {}): AiUsagePolicy {
  return {
    monthly_budget_usd: '5.0000',
    max_output_tokens: 1024,
    max_concurrent_requests: 2,
    max_requests_per_minute: 10,
    unpriced_model_policy: 'block',
    guarantee: 'local_estimate_only',
    updated_at: '2026-11-02T00:00:00Z',
    ...overrides,
  }
}

export function pricingRow(overrides: Partial<AiModelPricingRow> = {}): AiModelPricingRow {
  return {
    provider: 'anthropic',
    model: 'claude-x',
    input_usd_per_mtok: '3.000000',
    output_usd_per_mtok: '15.000000',
    updated_at: '2026-11-02T00:00:00Z',
    ...overrides,
  }
}

export function inferencePreview(overrides: Partial<AiInferenceTestPreview> = {}): AiInferenceTestPreview {
  return {
    provider: 'anthropic',
    model: 'claude-alpha-20260101',
    action: 'inference_test',
    content: 'Reply with the single word: OK',
    max_output_tokens: 1024,
    pricing_known: true,
    estimated_max_cost_usd: '0.015360',
    policy_decision: 'allowed',
    destination_note: 'Sent to Anthropic (api.anthropic.com)',
    ...overrides,
  }
}

export function outboundPreview(overrides: Partial<OutboundPreview> = {}): OutboundPreview {
  return {
    provider: 'anthropic',
    model: 'claude-test',
    destination_note: 'Sent to Anthropic (api.anthropic.com)',
    items: [
      {
        type: 'report',
        id: '0b7d5a5e-0000-4000-8000-0000000000aa',
        label: 'Weekly summary',
        tlp: 'green',
        included: true,
        excluded_reason: null,
        redactions: 2,
      },
      {
        type: 'observable',
        id: '0b7d5a5e-0000-4000-8000-0000000000bb',
        label: '1.2.3.4',
        tlp: 'red',
        included: false,
        excluded_reason: 'tlp_restricted',
        redactions: 0,
      },
    ],
    content: 'UNTRUSTED DATA BLOCK\n[REDACTED]',
    content_chars: 31,
    digest: 'sha256:abc',
    // Far future so tests are not time-sensitive unless they mean to be.
    expires_at: '2099-01-01T00:00:00Z',
    ...overrides,
  }
}

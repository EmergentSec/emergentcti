import { describe, expect, it } from 'vitest'
import {
  absDecimal,
  describeActionsInScope,
  displayCostWithUnknown,
  displayRecordCost,
  displayTokenCount,
  displayTokensWithUnknown,
  displayUnknown,
  displayUsdEstimate,
  formatUtcTimestamp,
  inferenceTestBlockReason,
  isValidUsageMonth,
} from './aiDisplay'
import { usageRecord } from '@/test/fixtures/ai'

describe('aiDisplay', () => {
  it('renders Unknown for nullish values', () => {
    expect(displayUnknown(null)).toBe('Unknown')
    expect(displayTokenCount(null)).toBe('Unknown')
    expect(displayUsdEstimate(undefined)).toBe('Unknown')
  })

  it('labels costs as estimates', () => {
    expect(displayUsdEstimate('1.2500')).toBe('$1.2500 est.')
  })

  it('maps inference block reasons', () => {
    expect(inferenceTestBlockReason('allowed')).toBeNull()
    expect(inferenceTestBlockReason('blocked_unpriced')).toMatch(/pricing/)
    expect(inferenceTestBlockReason('over_budget')).toMatch(/budget/)
  })
})

describe('displayCostWithUnknown (H1)', () => {
  it('never shows a bare $0 when costs are unknown', () => {
    expect(displayCostWithUnknown({ estimated_cost_usd: '0.000000', cost_unknown_requests: 1 })).toBe(
      'Unknown (1 request)',
    )
    expect(displayCostWithUnknown({ estimated_cost_usd: '0.000000', cost_unknown_requests: 3 })).toBe(
      'Unknown (3 requests)',
    )
  })

  it('adds the unknown count to a known partial sum', () => {
    expect(displayCostWithUnknown({ estimated_cost_usd: '0.000051', cost_unknown_requests: 2 })).toBe(
      '$0.000051 est. + 2 unknown',
    )
  })

  it('is a plain estimate when everything is known, including a genuine zero', () => {
    expect(displayCostWithUnknown({ estimated_cost_usd: '1.250000', cost_unknown_requests: 0 })).toBe('$1.250000 est.')
    expect(displayCostWithUnknown({ estimated_cost_usd: '0.000000', cost_unknown_requests: 0 })).toBe('$0.000000 est.')
  })
})

describe('displayTokensWithUnknown (H1 tokens)', () => {
  it('flags unknown token requests', () => {
    expect(displayTokensWithUnknown(0, 2)).toBe('Unknown (2 requests)')
    expect(displayTokensWithUnknown(40, 1)).toBe('40 + 1 unknown')
    expect(displayTokensWithUnknown(40, 0)).toBe('40')
  })
})

describe('absDecimal (L1)', () => {
  it('drops the sign without a float round-trip', () => {
    expect(absDecimal('-0.500000')).toBe('0.500000')
    expect(absDecimal('12.340000')).toBe('12.340000')
  })
})

describe('isValidUsageMonth (M2)', () => {
  it('accepts only YYYY-MM from 2000-01 to 9999-11, like the backend', () => {
    expect(isValidUsageMonth('2026-11')).toBe(true)
    expect(isValidUsageMonth('2000-01')).toBe(true)
    expect(isValidUsageMonth('9999-11')).toBe(true)
    // The backend rejects 9999-12: its exclusive end would be year 10000.
    expect(isValidUsageMonth('9999-12')).toBe(false)
    for (const bad of ['', '2026-13', '2026-00', '1999-12', '2026-1', 'nov 2026', '2026-11-01']) {
      expect(isValidUsageMonth(bad)).toBe(false)
    }
  })
})

describe('formatUtcTimestamp (L2)', () => {
  it('formats ISO timestamps in UTC', () => {
    expect(formatUtcTimestamp('2026-11-02T14:05:09.123456Z')).toBe('2026-11-02 14:05 UTC')
    expect(formatUtcTimestamp('2026-11-02T23:30:00-02:00')).toBe('2026-11-03 01:30 UTC')
    expect(formatUtcTimestamp('not a date')).toBe('not a date')
  })
})

describe('describeActionsInScope (L5)', () => {
  it('labels known actions and passes through new ones', () => {
    expect(describeActionsInScope(['inference_test'])).toBe('In scope: connection inference tests.')
    expect(describeActionsInScope(['inference_test', 'summarize'])).toBe(
      'In scope: connection inference tests, summarize.',
    )
    expect(describeActionsInScope([])).toBe('In scope: no actions.')
  })
})

describe('displayRecordCost (L2, H2 reserved_usd)', () => {
  it('distinguishes known, reserved, non-billed and unknown costs', () => {
    expect(displayRecordCost(usageRecord())).toBe('$0.000051 est.')
    expect(displayRecordCost(usageRecord({ status: 'reserved', reserved_usd: '0.015360', cost_usd: null }))).toBe(
      'Reserved $0.015360 est.',
    )
    expect(displayRecordCost(usageRecord({ status: 'failed', billable: 'no', cost_usd: null }))).toBe('Not billed')
    expect(displayRecordCost(usageRecord({ status: 'failed', billable: 'unknown', cost_usd: null }))).toBe('Unknown')
  })
})

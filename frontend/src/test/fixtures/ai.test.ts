import { describe, expect, it } from 'vitest'
import {
  BACKEND_FIELDS,
  byDay,
  byProviderModel,
  inferencePreview,
  outboundPreview,
  pricingRow,
  usagePolicy,
  usageRecord,
  usageReport,
  usageTotals,
} from './ai'

/**
 * Guards the fixtures themselves (M7/H2): each one must carry exactly the
 * backend schema's fields, so a UI test can't pass against a shape the API
 * never sends (as the old `estimated_cost_usd: null` fixture did).
 */
describe('AI fixtures match backend schemas', () => {
  const keys = (o: object) => Object.keys(o).sort()
  const fields = (f: readonly string[]) => [...f].sort()

  it('usage totals and breakdown rows', () => {
    expect(keys(usageTotals())).toEqual(fields(BACKEND_FIELDS.AiUsageTotals))
    expect(keys(byProviderModel('p', 'm'))).toEqual(fields([...BACKEND_FIELDS.AiUsageTotals, 'provider', 'model']))
    expect(keys(byDay('2026-11-02'))).toEqual(fields([...BACKEND_FIELDS.AiUsageTotals, 'date']))
    expect(keys(usageReport())).toEqual(fields(BACKEND_FIELDS.AiUsageReport))
  })

  it('estimated_cost_usd is a non-null 6-dp string', () => {
    expect(usageTotals().estimated_cost_usd).toMatch(/^\d+\.\d{6}$/)
  })

  it('records, policy, pricing and previews', () => {
    expect(keys(usageRecord())).toEqual(fields(BACKEND_FIELDS.AiUsageRecordItem))
    expect(keys(usagePolicy())).toEqual(fields(BACKEND_FIELDS.AiUsagePolicyOut))
    expect(keys(pricingRow())).toEqual(fields(BACKEND_FIELDS.AiModelPricingOut))
    expect(keys(inferencePreview())).toEqual(fields(BACKEND_FIELDS.AiInferencePreview))
    expect(keys(outboundPreview())).toEqual(fields(BACKEND_FIELDS.OutboundPreview))
  })

  it('outbound TLP markings are the backend lowercase values', () => {
    for (const item of outboundPreview().items) {
      expect(['clear', 'green', 'amber', 'amber+strict', 'red', null]).toContain(item.tlp)
    }
  })
})

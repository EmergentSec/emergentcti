import { afterEach, describe, expect, it, vi } from 'vitest'
import api from './client'
import {
  auditOutcomeBadgeVariant,
  auditOutcomeLabel,
  buildAuditParams,
  formatAuditSummaryEntries,
  getAuditEvents,
  getAuditMeta,
} from './audit'

afterEach(() => vi.restoreAllMocks())

describe('buildAuditParams', () => {
  it('omits empty values', () => {
    expect(buildAuditParams({ page: 1, actor_id: '' })).toEqual({ page: 1 })
  })

  it('passes scalar filters', () => {
    const params = buildAuditParams({
      since: '2026-01-01T00:00:00Z',
      until: '2026-02-01T00:00:00Z',
      actor_type: 'user',
      actor_id: 'u-1',
      resource_type: 'report',
      resource_id: 'r-1',
      page: 2,
      size: 25,
    })
    expect(params).toEqual({
      since: '2026-01-01T00:00:00Z',
      until: '2026-02-01T00:00:00Z',
      actor_type: 'user',
      actor_id: 'u-1',
      resource_type: 'report',
      resource_id: 'r-1',
      page: 2,
      size: 25,
    })
  })

  it('repeats action keys for multi-select', () => {
    const params = buildAuditParams({
      action: ['report.update', 'report.delete'],
      page: 1,
    })
    expect(params).toBeInstanceOf(URLSearchParams)
    const search = params as URLSearchParams
    expect(search.getAll('action')).toEqual(['report.update', 'report.delete'])
    expect(search.get('page')).toBe('1')
  })

  it('repeats outcome keys', () => {
    const params = buildAuditParams({
      outcome: ['succeeded', 'denied'],
    })
    expect(params).toBeInstanceOf(URLSearchParams)
    const search = params as URLSearchParams
    expect(search.getAll('outcome')).toEqual(['succeeded', 'denied'])
  })

  it('accepts a single action or outcome as a scalar', () => {
    const params = buildAuditParams({ action: 'export.download', outcome: 'initiated' })
    expect(params).toBeInstanceOf(URLSearchParams)
    const search = params as URLSearchParams
    expect(search.getAll('action')).toEqual(['export.download'])
    expect(search.getAll('outcome')).toEqual(['initiated'])
  })
})

describe('audit API routes', () => {
  it('calls GET /audit/events and /audit/meta', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, size: 50, pages: 1 } })
    await getAuditEvents({ page: 1, size: 50 })
    expect(get).toHaveBeenCalledWith('/audit/events', {
      params: { page: 1, size: 50 },
    })

    get.mockResolvedValueOnce({ data: { actions: [], actor_types: [], outcomes: [], resource_types: [], retention_days: 365 } })
    await getAuditMeta()
    expect(get).toHaveBeenCalledWith('/audit/meta')
  })
})

describe('auditOutcomeLabel and badge variants', () => {
  it('labels every outcome', () => {
    const outcomes = ['succeeded', 'failed', 'denied', 'initiated', 'completed', 'interrupted'] as const
    for (const o of outcomes) {
      expect(auditOutcomeLabel(o)).toBe(o)
      expect(auditOutcomeBadgeVariant(o)).toBeTruthy()
    }
  })
})

describe('formatAuditSummaryEntries', () => {
  it('JSON-stringifies nested values and renders strings literally', () => {
    const entries = formatAuditSummaryEntries({
      note: '<script>alert(1)</script>',
      nested: { a: 1 },
    })
    expect(entries).toEqual([
      { key: 'note', value: '<script>alert(1)</script>' },
      { key: 'nested', value: '{"a":1}' },
    ])
  })
})

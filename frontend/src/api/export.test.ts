import { describe, expect, it } from 'vitest'
import { blocklistUrl, jsonExportUrl } from './export'

describe('blocklistUrl', () => {
  it('returns base path for empty filters', () => {
    expect(blocklistUrl('ip-addr', {})).toBe('/api/v1/export/blocklist/ip-addr')
  })

  it('adds confidence_min param when > 0', () => {
    expect(blocklistUrl('domain-name', { confidence_min: 50 })).toBe(
      '/api/v1/export/blocklist/domain-name?confidence_min=50',
    )
  })

  it('omits confidence_min when value is 0', () => {
    expect(blocklistUrl('ip-addr', { confidence_min: 0 })).toBe('/api/v1/export/blocklist/ip-addr')
  })

  it('adds feed_id when source is a UUID', () => {
    expect(blocklistUrl('url', { source: 'abc-123' })).toBe(
      '/api/v1/export/blocklist/url?feed_id=abc-123',
    )
  })

  it('omits feed_id when source is "manual"', () => {
    expect(blocklistUrl('ip-addr', { source: 'manual' })).toBe(
      '/api/v1/export/blocklist/ip-addr',
    )
  })

  it('omits feed_id when source is empty string', () => {
    expect(blocklistUrl('ip-addr', { source: '' })).toBe('/api/v1/export/blocklist/ip-addr')
  })

  it('combines confidence_min and feed_id', () => {
    expect(blocklistUrl('ip-addr', { confidence_min: 70, source: 'feed-xyz' })).toBe(
      '/api/v1/export/blocklist/ip-addr?confidence_min=70&feed_id=feed-xyz',
    )
  })

  it('builds correct paths for all three blocklist obs types', () => {
    expect(blocklistUrl('ip-addr', {})).toContain('/blocklist/ip-addr')
    expect(blocklistUrl('domain-name', {})).toContain('/blocklist/domain-name')
    expect(blocklistUrl('url', {})).toContain('/blocklist/url')
  })
})

describe('jsonExportUrl', () => {
  it('returns base path for empty filters', () => {
    expect(jsonExportUrl({})).toBe('/api/v1/export/json')
  })

  it('adds confidence_min when > 0', () => {
    expect(jsonExportUrl({ confidence_min: 80 })).toBe('/api/v1/export/json?confidence_min=80')
  })

  it('omits confidence_min when 0', () => {
    expect(jsonExportUrl({ confidence_min: 0 })).toBe('/api/v1/export/json')
  })

  it('omits feed_id for manual source', () => {
    expect(jsonExportUrl({ source: 'manual' })).toBe('/api/v1/export/json')
  })

  it('adds feed_id for non-manual source UUID', () => {
    expect(jsonExportUrl({ source: 'feed-abc' })).toBe('/api/v1/export/json?feed_id=feed-abc')
  })

  it('combines both params', () => {
    expect(jsonExportUrl({ confidence_min: 60, source: 'my-feed' })).toBe(
      '/api/v1/export/json?confidence_min=60&feed_id=my-feed',
    )
  })
})

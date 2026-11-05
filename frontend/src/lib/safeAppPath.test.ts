import { describe, expect, it } from 'vitest'
import { entityDetailPath, feedsHighlightPath, isSafeAppPath, safeAppPath } from './safeAppPath'

describe('safeAppPath', () => {
  it('accepts normal internal paths', () => {
    expect(isSafeAppPath('/reports/abc')).toBe(true)
    expect(safeAppPath('/observables?q=test')).toBe('/observables?q=test')
  })

  it('rejects protocol-relative and backslash open-redirect patterns', () => {
    expect(isSafeAppPath('//evil.example')).toBe(false)
    expect(isSafeAppPath('/\\evil.example')).toBe(false)
    expect(safeAppPath('/\\evil.example')).toBeNull()
    expect(safeAppPath('/reports/\\evil')).toBeNull()
  })

  it('builds entity paths and rejects unsafe ids', () => {
    expect(entityDetailPath('/reports', 'r-1')).toBe('/reports/r-1')
    expect(entityDetailPath('/reports', '/\\evil')).toBeNull()
    expect(entityDetailPath('/observables', '..')).toBe('/observables/..')
  })

  it('builds feeds highlight query paths', () => {
    expect(feedsHighlightPath('feed-1')).toBe('/feeds?feed=feed-1')
    expect(feedsHighlightPath('/\\x')).toBeNull()
  })
})

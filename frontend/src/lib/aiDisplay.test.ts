import { describe, expect, it } from 'vitest'
import { displayTokenCount, displayUnknown, displayUsdEstimate, inferenceTestBlockReason } from './aiDisplay'

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
  })
})

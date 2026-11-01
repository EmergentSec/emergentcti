import { describe, expect, it } from 'vitest'
import { needsTlpChangeReason, formatExcludedByTlp } from '@/lib/tlp'

describe('needsTlpChangeReason', () => {
  it('requires reason when loosening rank', () => {
    expect(needsTlpChangeReason('red', 'green')).toBe(true)
    expect(needsTlpChangeReason('amber', 'clear')).toBe(true)
  })

  it('requires reason when clearing to unspecified', () => {
    expect(needsTlpChangeReason('green', null)).toBe(true)
  })

  it('does not require reason when tightening', () => {
    expect(needsTlpChangeReason('clear', 'red')).toBe(false)
    expect(needsTlpChangeReason(null, 'amber')).toBe(false)
  })
})

describe('formatExcludedByTlp', () => {
  it('formats non-zero counts as readable lines', () => {
    const lines = formatExcludedByTlp({
      unspecified: 0,
      clear: 0,
      green: 0,
      amber: 0,
      'amber+strict': 0,
      red: 3,
    })
    expect(lines).toEqual(['3 excluded: TLP:RED never leaves the application (indicators)'])
  })
})

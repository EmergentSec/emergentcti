import { describe, expect, it } from 'vitest'
import { buildListParams } from './listParams'

describe('buildListParams', () => {
  it('repeats tag and tlp keys', () => {
    const params = buildListParams({
      page: 1,
      tag: ['alpha', 'beta'],
      tlp: ['red', 'unspecified'],
    })
    expect(params).toBeInstanceOf(URLSearchParams)
    const search = params as URLSearchParams
    expect(search.getAll('tag')).toEqual(['alpha', 'beta'])
    expect(search.getAll('tlp')).toEqual(['red', 'unspecified'])
    expect(search.get('page')).toBe('1')
  })
})

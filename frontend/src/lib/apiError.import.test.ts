import { describe, expect, it } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import { importValidationErrorDetail, importValidationErrorMessage } from './apiError'

function http422(detail: unknown) {
  return new AxiosError('Request failed', '422', undefined, undefined, {
    status: 422,
    data: { detail },
  } as AxiosResponse)
}

/** Pinned contract shape from docs/superpowers/specs/2026-11-01-report-ioc-extraction.md */
const PINNED_DETAIL = [
  {
    type: 'greater_than_equal',
    loc: ['body', 'confidence'],
    msg: 'Input should be greater than or equal to 0',
    input: -1,
  },
  {
    type: 'not_a_candidate',
    loc: ['body', 'items'],
    msg: '2 item(s) are not valid candidates extracted from this report: url http://x, domain-name bad',
    items: [
      { index: 0, type: 'url', value: 'http://x' },
      { index: 1, type: 'domain-name', value: 'bad.example' },
    ],
  },
]

describe('importValidationErrorDetail', () => {
  it('parses the pinned FastAPI validation list', () => {
    const parsed = importValidationErrorDetail(http422(PINNED_DETAIL))
    expect(parsed?.messages).toEqual([
      'Input should be greater than or equal to 0',
      '2 item(s) are not valid candidates extracted from this report: url http://x, domain-name bad',
    ])
    expect(parsed?.highlightedItems).toEqual([
      { type: 'url', value: 'http://x' },
      { type: 'domain-name', value: 'bad.example' },
    ])
  })

  it('supports string detail', () => {
    const parsed = importValidationErrorDetail(http422('Item not_a_candidate: evil.example'))
    expect(parsed).toEqual({
      messages: ['Item not_a_candidate: evil.example'],
      highlightedItems: [],
    })
  })
})

describe('importValidationErrorMessage', () => {
  it('joins every entry msg', () => {
    expect(importValidationErrorMessage(http422(PINNED_DETAIL), 'Import failed')).toBe(
      'Input should be greater than or equal to 0\n2 item(s) are not valid candidates extracted from this report: url http://x, domain-name bad',
    )
  })
})

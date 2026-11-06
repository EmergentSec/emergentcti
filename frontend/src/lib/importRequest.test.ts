import { describe, expect, it } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import {
  IMPORT_TIMEOUT_MESSAGE,
  importFailureMessage,
  importSuccessMessage,
  isImportRequestTimeout,
} from './importRequest'

function httpError(status: number, detail: unknown) {
  return new AxiosError('Request failed', String(status), undefined, undefined, {
    status,
    data: { detail },
  } as AxiosResponse)
}

describe('isImportRequestTimeout', () => {
  it('matches an axios timeout and ignores other failures', () => {
    expect(
      isImportRequestTimeout(new AxiosError('timeout of 60000ms exceeded', 'ECONNABORTED')),
    ).toBe(true)
    expect(isImportRequestTimeout(new AxiosError('canceled', 'ECONNABORTED'))).toBe(false)
    expect(isImportRequestTimeout(httpError(500, 'boom'))).toBe(false)
    expect(isImportRequestTimeout(new Error('timeout'))).toBe(false)
  })
})

describe('importFailureMessage', () => {
  it('tells the analyst a timed-out import may have been saved', () => {
    const err = new AxiosError('timeout of 60000ms exceeded', 'ECONNABORTED')
    expect(importFailureMessage(err)).toBe(IMPORT_TIMEOUT_MESSAGE)
  })

  it('keeps server detail for a response error', () => {
    expect(importFailureMessage(httpError(404, 'Report not found'))).toBe('Report not found')
  })
})

describe('importSuccessMessage', () => {
  it('includes created, attributed, and already-linked counts', () => {
    expect(
      importSuccessMessage({ created: 2, attributed_existing: 0, already_attributed: 1 }),
    ).toBe('Import complete: 2 created, 0 attributed, 1 already linked')
  })
})

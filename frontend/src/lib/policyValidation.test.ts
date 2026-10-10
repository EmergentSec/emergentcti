import { describe, expect, it } from 'vitest'
import { validateAllowlistEntry, validateExportProfile } from './policyValidation'

const exact = { kind: 'exact' as const, value: '8.8.8.8', observableType: 'ip-addr' as const, reason: 'DNS' }
const profile = { name: 'Firewall', description: '', confidenceMin: '70', maxAgeDays: '' }

describe('validateAllowlistEntry', () => {
  it('accepts a complete exact entry', () => {
    expect(validateAllowlistEntry(exact)).toEqual({})
  })

  it('enforces the UTF-8 byte limit rather than only a character limit', () => {
    const literal = { ...exact, observableType: 'command-line' as const }
    expect(validateAllowlistEntry({ ...literal, value: 'é'.repeat(1024) })).toEqual({})
    expect(validateAllowlistEntry({ ...literal, value: 'é'.repeat(1025) }).value).toMatch(/2048 UTF-8/)
  })

  it.each(['*.example.com', 'https://example.com', 'example.com:443', 'a..b'])(
    'rejects malformed exact domains %s',
    (value) => {
      expect(validateAllowlistEntry({ ...exact, observableType: 'domain-name', value }).value).toBeTruthy()
    },
  )

  it('requires a type for exact entries only', () => {
    expect(validateAllowlistEntry({ ...exact, observableType: '' }).observableType).toBeTruthy()
    expect(
      validateAllowlistEntry({ kind: 'cidr', value: '10.0.0.0/8', observableType: '', reason: 'x' }),
    ).toEqual({})
  })

  it('requires a value and a non-blank reason', () => {
    const errors = validateAllowlistEntry({ ...exact, value: '  ', reason: '  ' })
    expect(errors.value).toBe('Value is required')
    expect(errors.reason).toBe('Reason is required')
  })

  it('rejects a reason longer than 500 characters', () => {
    expect(validateAllowlistEntry({ ...exact, reason: 'a'.repeat(500) }).reason).toBeUndefined()
    expect(validateAllowlistEntry({ ...exact, reason: 'a'.repeat(501) }).reason).toMatch(/500/)
  })

  it.each(['10.0.0.0/8', '192.168.1.7/24', '0.0.0.0/0', '2001:db8::/32', '::1/128'])(
    'accepts CIDR %s',
    (value) => {
      expect(validateAllowlistEntry({ kind: 'cidr', value, observableType: '', reason: 'x' })).toEqual({})
    },
  )

  it.each(['10.0.0.0', '10.0.0.0/33', '256.0.0.0/8', '2001:db8::/129', 'example.com/24', '10.0.0.0/8/9'])(
    'rejects CIDR %s',
    (value) => {
      expect(
        validateAllowlistEntry({ kind: 'cidr', value, observableType: '', reason: 'x' }).value,
      ).toBeTruthy()
    },
  )

  it.each(['example.com', 'Sub.Example.COM', 'example.com.'])('accepts domain suffix %s', (value) => {
    expect(
      validateAllowlistEntry({ kind: 'domain_suffix', value, observableType: '', reason: 'x' }),
    ).toEqual({})
  })

  it.each(['*.example.com', '.example.com', 'https://example.com', 'example.com/path', 'a..b', 'user@example.com'])(
    'rejects domain suffix %s',
    (value) => {
      expect(
        validateAllowlistEntry({ kind: 'domain_suffix', value, observableType: '', reason: 'x' }).value,
      ).toBeTruthy()
    },
  )
})

describe('validateExportProfile', () => {
  it('accepts defaults with a name', () => {
    expect(validateExportProfile(profile)).toEqual({})
  })

  it('requires a name of 1–100 characters', () => {
    expect(validateExportProfile({ ...profile, name: '   ' }).name).toBe('Name is required')
    expect(validateExportProfile({ ...profile, name: 'n'.repeat(100) }).name).toBeUndefined()
    expect(validateExportProfile({ ...profile, name: 'n'.repeat(101) }).name).toMatch(/100/)
  })

  it('limits the description to 500 characters', () => {
    expect(validateExportProfile({ ...profile, description: 'd'.repeat(501) }).description).toMatch(/500/)
  })

  it.each(['', '-1', '101', '7.5', 'abc'])('rejects minimum confidence %j', (confidenceMin) => {
    expect(validateExportProfile({ ...profile, confidenceMin }).confidenceMin).toBeTruthy()
  })

  it.each(['0', '100'])('accepts minimum confidence %s', (confidenceMin) => {
    expect(validateExportProfile({ ...profile, confidenceMin })).toEqual({})
  })

  it('accepts a blank maximum age and whole days >= 1, rejects everything else', () => {
    expect(validateExportProfile({ ...profile, maxAgeDays: '' })).toEqual({})
    expect(validateExportProfile({ ...profile, maxAgeDays: '1' })).toEqual({})
    expect(validateExportProfile({ ...profile, maxAgeDays: '0' }).maxAgeDays).toBeTruthy()
    expect(validateExportProfile({ ...profile, maxAgeDays: '-3' }).maxAgeDays).toBeTruthy()
    expect(validateExportProfile({ ...profile, maxAgeDays: '1.5' }).maxAgeDays).toBeTruthy()
    expect(validateExportProfile({ ...profile, maxAgeDays: '36500' })).toEqual({})
    expect(validateExportProfile({ ...profile, maxAgeDays: '36501' }).maxAgeDays).toBeTruthy()
    expect(validateExportProfile({ ...profile, maxAgeDays: '1000000000' }).maxAgeDays).toBeTruthy()
  })
})

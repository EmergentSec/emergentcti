import { describe, it, expect } from 'vitest'
import { validateFullAuthConfig } from './feedAuthValidation'

describe('validateFullAuthConfig', () => {
  it('accepts api_key shape', () => {
    expect(
      validateFullAuthConfig({
        auth_type: 'api_key',
        api_key_header: 'Key',
        api_key_value: 'secret',
      }),
    ).toBeNull()
  })

  it('rejects legacy api_key-only object', () => {
    expect(validateFullAuthConfig({ api_key: 'x' })).toMatch(/auth_type/)
  })

  it('requires {api_key} in URL for url_template', () => {
    expect(
      validateFullAuthConfig(
        { auth_type: 'url_template', api_key_value: 'k' },
        'https://example.com/list?key={api_key}',
      ),
    ).toBeNull()
    expect(
      validateFullAuthConfig(
        { auth_type: 'url_template', api_key_value: 'k' },
        'https://example.com/list',
      ),
    ).toMatch(/\{api_key\}/)
  })
})

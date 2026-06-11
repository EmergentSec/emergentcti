import { beforeEach, describe, expect, it } from 'vitest'
import { AxiosError } from 'axios'
import api from './client'

// Track requests reaching the (mocked) network layer
let requestLog: string[]

// Stubbed location — client.ts reads pathname and assigns href
let location: { pathname: string; href: string }

function install401Adapter() {
  api.defaults.adapter = async (config) => {
    requestLog.push(`${config.method?.toUpperCase()} ${config.url}`)
    const response = {
      data: { detail: 'Not authenticated' },
      status: 401,
      statusText: 'Unauthorized',
      headers: {},
      config,
    }
    // Custom adapters must reject on bad status themselves
    throw new AxiosError(
      'Request failed with status code 401',
      AxiosError.ERR_BAD_REQUEST,
      config,
      null,
      response
    )
  }
}

beforeEach(() => {
  requestLog = []
  location = { pathname: '/', href: '' }
  Object.defineProperty(window, 'location', {
    value: location,
    writable: true,
    configurable: true,
  })
  install401Adapter()
})

describe('401 refresh interceptor', () => {
  it('redirects to /login when refresh fails away from the login page', async () => {
    location.pathname = '/dashboard'

    await expect(api.get('/feeds')).rejects.toThrow()

    expect(requestLog).toContain('POST /auth/refresh')
    expect(location.href).toBe('/login')
  })

  it('does not navigate when refresh fails on the login page (no reload loop)', async () => {
    location.pathname = '/login'

    await expect(api.get('/auth/me')).rejects.toThrow()

    // Navigating to /login while already there forces a full page reload,
    // which remounts the app and restarts the /me -> /refresh cycle forever.
    expect(location.href).toBe('')
  })

  it('still attempts refresh exactly once so valid sessions can be restored', async () => {
    // An expired access token with a valid refresh cookie must go through
    // refresh-and-retry, or returning users would be logged out on reload.
    location.pathname = '/login'

    await expect(api.get('/auth/me')).rejects.toThrow()

    expect(requestLog).toEqual(['GET /auth/me', 'POST /auth/refresh'])
  })
})

import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { getConfig } from '@/api/settings'
import { GeneralSettings } from './GeneralSettings'

vi.mock('@/api/settings', () => ({
  getConfig: vi.fn().mockResolvedValue({
    instance_name: 'EmergentCTI Dev',
    confidence_decay_enabled: true,
    confidence_decay_days: 30,
    confidence_decay_rate: 5,
    confidence_decay_floor: 10,
    confidence_decay_interval_hours: 24,
    observable_retention_days: 90,
    default_export_format: 'STIX 2.1',
  }),
}))

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

afterEach(cleanup)

describe('GeneralSettings', () => {
  it('renders the instance name', async () => {
    render(<GeneralSettings />, { wrapper: makeWrapper() })
    expect(await screen.findByText('EmergentCTI Dev')).toBeTruthy()
  })

  it('renders the linear decay text with rate, days, and floor', async () => {
    render(<GeneralSettings />, { wrapper: makeWrapper() })
    expect(await screen.findByText('-5/wk after 30d, floor 10')).toBeTruthy()
  })

  it('does NOT mention "half-life"', async () => {
    render(<GeneralSettings />, { wrapper: makeWrapper() })
    await screen.findByText('EmergentCTI Dev')
    expect(screen.queryByText(/half-life/i)).toBeNull()
  })

  it('renders observable retention days', async () => {
    render(<GeneralSettings />, { wrapper: makeWrapper() })
    expect(await screen.findByText('90 days')).toBeTruthy()
  })

  it('describes retention as irreversible daily deletion that includes allowlisted rows', async () => {
    render(<GeneralSettings />, { wrapper: makeWrapper() })
    expect(
      await screen.findByText(
        'A daily job permanently deletes observables not seen for more than 90 days, including manually added and allowlisted ones. Deleted observables cannot be restored.',
      ),
    ).toBeTruthy()
  })

  it('shows retention as Disabled when configured as 0', async () => {
    const config = await getConfig()
    vi.mocked(getConfig).mockResolvedValueOnce({ ...config, observable_retention_days: 0 })
    render(<GeneralSettings />, { wrapper: makeWrapper() })
    expect(await screen.findByText('Disabled')).toBeTruthy()
    expect(screen.queryByText('0 days')).toBeNull()
    expect(screen.getByText(/No observables are deleted by age/)).toBeTruthy()
  })

  it('renders default export format', async () => {
    render(<GeneralSettings />, { wrapper: makeWrapper() })
    expect(await screen.findByText('STIX 2.1')).toBeTruthy()
  })
})

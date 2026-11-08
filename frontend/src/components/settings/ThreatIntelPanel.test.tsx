import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, type AxiosResponse } from 'axios'
import { ThreatIntelPanel } from './ThreatIntelPanel'
import * as threatIntelApi from '@/api/threatIntel'

vi.mock('@/api/threatIntel', () => ({
  fetchThreatIntelFeeds: vi.fn(),
  generateThreatIntelReport: vi.fn(),
  listThreatIntelSkills: vi.fn(),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

const api = vi.mocked(threatIntelApi)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ThreatIntelPanel', () => {
  it('keeps the fetch failure reason visible after the toast', async () => {
    api.listThreatIntelSkills.mockResolvedValue([])
    const detail = 'Threat-intel data directory data is not writable (Permission denied).'
    const error = new AxiosError('Request failed with status code 500')
    error.response = { status: 500, data: { detail } } as AxiosResponse
    api.fetchThreatIntelFeeds.mockRejectedValue(error)

    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <ThreatIntelPanel />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Fetch feeds' }))
    expect((await screen.findByRole('alert')).textContent).toBe(detail)
  })
})

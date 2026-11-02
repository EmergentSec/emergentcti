import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiUsagePanel } from './AiUsage'
import * as aiApi from '@/api/ai'
import type { AiUsageResponse } from '@/types/ai'

vi.mock('@/api/ai', () => ({
  getAiUsage: vi.fn(),
  getAiUsageRecords: vi.fn(),
}))

const api = vi.mocked(aiApi)

const usageNoBudget: AiUsageResponse = {
  period: { month: '2026-11', start: '2026-11-01T00:00:00Z', end: '2026-12-01T00:00:00Z', timezone: 'UTC' },
  actions_in_scope: ['inference_test'],
  guarantee: 'local_estimate_only',
  totals: {
    requests: 2,
    succeeded: 1,
    failed: 1,
    cancelled: 0,
    reserved: 0,
    input_tokens: 10,
    output_tokens: 5,
    token_unknown_requests: 1,
    estimated_cost_usd: null,
    cost_unknown_requests: 1,
    committed_usd: '0.5000',
  },
  budget: { monthly_budget_usd: null, committed_usd: '0.5000', remaining_usd: null },
  by_provider_model: [],
  by_day: [],
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AiUsagePanel />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AiUsagePanel', () => {
  it('shows Unknown for null estimated cost and no budget bar label', async () => {
    api.getAiUsage.mockResolvedValue(usageNoBudget)
    api.getAiUsageRecords.mockResolvedValue({ items: [], next_before: null })
    renderPanel()
    const section = await screen.findByRole('region', { name: 'AI usage' })
    expect(await within(section).findByText('No budget set')).toBeTruthy()
    await waitFor(() => expect(within(section).getAllByText('Unknown').length).toBeGreaterThan(0))
    expect(within(section).getByText(/1 requests with unknown cost/)).toBeTruthy()
  })

  it('renders budget bar when monthly budget is set', async () => {
    api.getAiUsage.mockResolvedValue({
      ...usageNoBudget,
      budget: { monthly_budget_usd: '10.0000', committed_usd: '2.5000', remaining_usd: '7.5000' },
      totals: { ...usageNoBudget.totals, estimated_cost_usd: '2.5000', cost_unknown_requests: 0 },
    })
    api.getAiUsageRecords.mockResolvedValue({ items: [], next_before: null })
    renderPanel()
    const section = await screen.findByRole('region', { name: 'AI usage' })
    expect(await within(section).findByRole('meter', { name: 'Budget committed' })).toBeTruthy()
    expect(within(section).getAllByText(/\$2\.5000 est\./).length).toBeGreaterThan(0)
  })
})

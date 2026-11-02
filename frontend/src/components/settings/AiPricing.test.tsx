import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiPricingTable } from './AiPricing'
import * as aiApi from '@/api/ai'

vi.mock('@/api/ai', () => ({
  getAiPricing: vi.fn(),
  putAiPricingRow: vi.fn(),
  deleteAiPricingRow: vi.fn(),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

const api = vi.mocked(aiApi)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AiPricingTable', () => {
  it('adds pricing via PUT and deletes a row', async () => {
    api.getAiPricing.mockResolvedValue({
      items: [{ provider: 'anthropic', model: 'claude-x', input_usd_per_mtok: '3', output_usd_per_mtok: '15', updated_at: '2026-11-02T00:00:00Z' }],
    })
    api.putAiPricingRow.mockResolvedValue({
      provider: 'openai',
      model: 'gpt-z',
      input_usd_per_mtok: '1',
      output_usd_per_mtok: '2',
      updated_at: '2026-11-02T00:00:00Z',
    })
    api.deleteAiPricingRow.mockResolvedValue(undefined)

    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <AiPricingTable />
      </QueryClientProvider>,
    )

    const section = await screen.findByRole('region', { name: 'Model pricing' })
    fireEvent.change(within(section).getByLabelText('Provider'), { target: { value: 'openai' } })
    fireEvent.change(within(section).getByLabelText('Model ID'), { target: { value: 'gpt-z' } })
    fireEvent.change(within(section).getByLabelText('Input $/Mtok'), { target: { value: '1' } })
    fireEvent.change(within(section).getByLabelText('Output $/Mtok'), { target: { value: '2' } })
    fireEvent.click(within(section).getByRole('button', { name: 'Add / update' }))

    await waitFor(() =>
      expect(api.putAiPricingRow).toHaveBeenCalledWith('openai', 'gpt-z', {
        input_usd_per_mtok: '1',
        output_usd_per_mtok: '2',
      }),
    )

    fireEvent.click(within(section).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(api.deleteAiPricingRow).toHaveBeenCalledWith('anthropic', 'claude-x'))
  })
})

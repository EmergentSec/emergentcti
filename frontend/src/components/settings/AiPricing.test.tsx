import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiPricingTable } from './AiPricing'
import * as aiApi from '@/api/ai'
import { pricingRow } from '@/test/fixtures/ai'

vi.mock('@/api/ai', () => ({
  getAiPricing: vi.fn(),
  putAiPricingRow: vi.fn(),
  deleteAiPricingRow: vi.fn(),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

const api = vi.mocked(aiApi)

function renderTable() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AiPricingTable />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AiPricingTable', () => {
  it('adds pricing via PUT', async () => {
    api.getAiPricing.mockResolvedValue({ items: [pricingRow()] })
    api.putAiPricingRow.mockResolvedValue(pricingRow({ provider: 'openai', model: 'gpt-z' }))
    renderTable()

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
  })

  it('edits a row by pre-filling the form with its key locked (L3)', async () => {
    api.getAiPricing.mockResolvedValue({
      items: [pricingRow(), pricingRow({ provider: 'openrouter', model: 'vendor/model', updated_at: null })],
    })
    api.putAiPricingRow.mockResolvedValue(pricingRow({ provider: 'openrouter', model: 'vendor/model' }))
    renderTable()
    const section = await screen.findByRole('region', { name: 'Model pricing' })

    fireEvent.click(await within(section).findByRole('button', { name: 'Edit pricing for openrouter/vendor/model' }))
    const providerSel = within(section).getByLabelText('Provider') as HTMLSelectElement
    const modelInput = within(section).getByLabelText('Model ID') as HTMLInputElement
    expect(providerSel.value).toBe('openrouter')
    expect(providerSel.disabled).toBe(true)
    expect(modelInput.value).toBe('vendor/model')
    expect(modelInput.readOnly).toBe(true)
    expect((within(section).getByLabelText('Input $/Mtok') as HTMLInputElement).value).toBe('3.000000')

    fireEvent.change(within(section).getByLabelText('Output $/Mtok'), { target: { value: '20' } })
    fireEvent.click(within(section).getByRole('button', { name: 'Save changes' }))
    await waitFor(() =>
      expect(api.putAiPricingRow).toHaveBeenCalledWith('openrouter', 'vendor/model', {
        input_usd_per_mtok: '3.000000',
        output_usd_per_mtok: '20',
      }),
    )
    // Form returns to add mode after saving.
    expect(await within(section).findByRole('button', { name: 'Add / update' })).toBeTruthy()
    expect(modelInput.value).toBe('')
  })

  it('asks for confirmation before deleting, with a per-row accessible name (L3)', async () => {
    api.getAiPricing.mockResolvedValue({ items: [pricingRow(), pricingRow({ model: 'claude-y' })] })
    api.deleteAiPricingRow.mockResolvedValue(undefined)
    renderTable()
    const section = await screen.findByRole('region', { name: 'Model pricing' })

    fireEvent.click(await within(section).findByRole('button', { name: 'Delete pricing for anthropic/claude-y' }))
    expect(api.deleteAiPricingRow).not.toHaveBeenCalled()
    let dialog = screen.getByRole('dialog', { name: 'Delete pricing row?' })
    expect(within(dialog).getByText('anthropic/claude-y')).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(api.deleteAiPricingRow).not.toHaveBeenCalled()

    fireEvent.click(within(section).getByRole('button', { name: 'Delete pricing for anthropic/claude-y' }))
    dialog = screen.getByRole('dialog', { name: 'Delete pricing row?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete pricing' }))
    await waitFor(() => expect(api.deleteAiPricingRow).toHaveBeenCalledWith('anthropic', 'claude-y'))
    expect(api.deleteAiPricingRow).toHaveBeenCalledTimes(1)
  })

  it('shows an empty state when there are no pricing rows (L3)', async () => {
    api.getAiPricing.mockResolvedValue({ items: [] })
    renderTable()
    const section = await screen.findByRole('region', { name: 'Model pricing' })
    expect(await within(section).findByText(/No pricing rows yet/)).toBeTruthy()
  })
})

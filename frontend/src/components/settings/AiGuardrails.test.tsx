import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiGuardrailsForm } from './AiGuardrails'
import * as aiApi from '@/api/ai'
import { AI_GUARDRAILS_NOTICE } from '@/lib/aiCopy'
import { usagePolicy } from '@/test/fixtures/ai'
import { AxiosError, type AxiosResponse } from 'axios'

vi.mock('@/api/ai', () => ({
  getAiUsagePolicy: vi.fn(),
  putAiUsagePolicy: vi.fn(),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

const api = vi.mocked(aiApi)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AiGuardrailsForm />
    </QueryClientProvider>,
  )
}

describe('AiGuardrailsForm', () => {
  it('shows persistent billing notice and submits PUT payload', async () => {
    api.getAiUsagePolicy.mockResolvedValue(usagePolicy())
    api.putAiUsagePolicy.mockResolvedValue(
      usagePolicy({ monthly_budget_usd: null, max_output_tokens: 2048, unpriced_model_policy: 'permit' }),
    )

    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <AiGuardrailsForm />
      </QueryClientProvider>,
    )

    const section = await screen.findByRole('region', { name: 'Spending guardrails' })
    expect(await within(section).findByText(AI_GUARDRAILS_NOTICE)).toBeTruthy()

    const budget = await within(section).findByLabelText('Monthly budget (USD, blank = none)')
    fireEvent.change(budget, { target: { value: '' } })
    fireEvent.change(await within(section).findByLabelText('Max output tokens'), { target: { value: '2048' } })
    fireEvent.click(within(section).getByLabelText('Permit (estimate unknown cost)'))
    fireEvent.click(within(section).getByRole('button', { name: 'Save guardrails' }))

    await waitFor(() =>
      expect(api.putAiUsagePolicy).toHaveBeenCalledWith({
        monthly_budget_usd: null,
        max_output_tokens: 2048,
        max_concurrent_requests: 2,
        max_requests_per_minute: 10,
        unpriced_model_policy: 'permit',
      }),
    )
  })

  it('shows validation error for out-of-range tokens', async () => {
    api.getAiUsagePolicy.mockResolvedValue(usagePolicy({ monthly_budget_usd: null }))
    renderForm()
    const section = await screen.findByRole('region', { name: 'Spending guardrails' })
    const tokens = await within(section).findByLabelText('Max output tokens')
    fireEvent.change(tokens, { target: { value: '99999' } })
    fireEvent.submit(tokens.closest('form')!)
    expect(await within(section).findByText(/between 1 and 32000/)).toBeTruthy()
    expect(api.putAiUsagePolicy).not.toHaveBeenCalled()
  })

  it('shows the load error instead of an endless spinner when the policy GET fails (M1)', async () => {
    api.getAiUsagePolicy.mockRejectedValue(
      new AxiosError('Request failed', '500', undefined, undefined, { status: 500, data: {} } as AxiosResponse),
    )
    renderForm()
    const section = await screen.findByRole('region', { name: 'Spending guardrails' })
    expect(await within(section).findByRole('alert')).toBeTruthy()
    expect(within(section).queryByRole('status')).toBeNull()
    expect(within(section).queryByLabelText('Max output tokens')).toBeNull()
    // The non-guarantee notice stays visible even on error.
    expect(within(section).getByText(AI_GUARDRAILS_NOTICE)).toBeTruthy()
  })

  it('accepts a policy that has never been saved (updated_at null)', async () => {
    api.getAiUsagePolicy.mockResolvedValue(usagePolicy({ updated_at: null, monthly_budget_usd: null }))
    renderForm()
    const section = await screen.findByRole('region', { name: 'Spending guardrails' })
    expect(await within(section).findByLabelText('Max output tokens')).toBeTruthy()
  })

  it('rejects a budget above the backend maximum and exponent-style integers (L6)', async () => {
    api.getAiUsagePolicy.mockResolvedValue(usagePolicy())
    renderForm()
    const section = await screen.findByRole('region', { name: 'Spending guardrails' })
    const budget = await within(section).findByLabelText('Monthly budget (USD, blank = none)')
    const form = budget.closest('form')!

    fireEvent.change(budget, { target: { value: '100000000' } })
    fireEvent.submit(form)
    expect(await within(section).findByText(/can't exceed 99999999\.9999/)).toBeTruthy()

    fireEvent.change(budget, { target: { value: '99999999.9999' } })
    fireEvent.change(within(section).getByLabelText('Max requests / minute'), { target: { value: '1e2' } })
    fireEvent.submit(form)
    expect(await within(section).findByText(/between 1 and 600/)).toBeTruthy()
    expect(api.putAiUsagePolicy).not.toHaveBeenCalled()
  })
})

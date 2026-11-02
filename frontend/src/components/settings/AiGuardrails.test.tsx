import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiGuardrailsForm } from './AiGuardrails'
import * as aiApi from '@/api/ai'
import { AI_GUARDRAILS_NOTICE } from '@/lib/aiCopy'

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

describe('AiGuardrailsForm', () => {
  it('shows persistent billing notice and submits PUT payload', async () => {
    api.getAiUsagePolicy.mockResolvedValue({
      monthly_budget_usd: '5.0000',
      max_output_tokens: 1024,
      max_concurrent_requests: 2,
      max_requests_per_minute: 10,
      unpriced_model_policy: 'block',
      updated_at: new Date().toISOString(),
      guarantee: 'local_estimate_only',
    })
    api.putAiUsagePolicy.mockResolvedValue({
      monthly_budget_usd: null,
      max_output_tokens: 2048,
      max_concurrent_requests: 3,
      max_requests_per_minute: 20,
      unpriced_model_policy: 'permit',
      updated_at: new Date().toISOString(),
      guarantee: 'local_estimate_only',
    })

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
    api.getAiUsagePolicy.mockResolvedValue({
      monthly_budget_usd: null,
      max_output_tokens: 1024,
      max_concurrent_requests: 2,
      max_requests_per_minute: 10,
      unpriced_model_policy: 'block',
      updated_at: new Date().toISOString(),
      guarantee: 'local_estimate_only',
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <AiGuardrailsForm />
      </QueryClientProvider>,
    )
    const section = await screen.findByRole('region', { name: 'Spending guardrails' })
    const tokens = await within(section).findByLabelText('Max output tokens')
    fireEvent.change(tokens, { target: { value: '99999' } })
    fireEvent.submit(tokens.closest('form')!)
    expect(await within(section).findByText(/between 1 and 32000/)).toBeTruthy()
    expect(api.putAiUsagePolicy).not.toHaveBeenCalled()
  })
})

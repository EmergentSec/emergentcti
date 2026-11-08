/**
 * Inference-test confirm dialog against the REAL React Query hooks (only the
 * HTTP layer is mocked), so preview enablement and staleness are exercised.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiSettings } from './AiSettings'
import * as aiApi from '@/api/ai'
import type { AiInferenceTestPreview, AiProviderStatus } from '@/types/ai'
import { inferencePreview, usagePolicy, usageReport } from '@/test/fixtures/ai'

vi.mock('@/api/ai', () => ({
  getAiSettings: vi.fn(),
  putAiProviderKey: vi.fn(),
  deleteAiProvider: vi.fn(),
  checkAiProvider: vi.fn(),
  getAiModels: vi.fn(),
  runAiInferenceTest: vi.fn(),
  getAiInferenceTestPreview: vi.fn(),
  putAiDefault: vi.fn(),
  deleteAiDefault: vi.fn(),
  getAiUsage: vi.fn(),
  getAiUsageRecords: vi.fn(),
  getAiUsagePolicy: vi.fn(),
  putAiUsagePolicy: vi.fn(),
  getAiPricing: vi.fn(),
  putAiPricingRow: vi.fn(),
  deleteAiPricingRow: vi.fn(),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

const api = vi.mocked(aiApi)
const MODEL = 'claude-alpha-20260101'

function status(provider: AiProviderStatus['provider'], configured: boolean): AiProviderStatus {
  return {
    provider,
    display_name: provider === 'anthropic' ? 'Anthropic' : provider,
    configured,
    key_hint: configured ? 'a1b2' : null,
    models_fetched_at: null,
    last_check_status: null,
    last_check_category: null,
    last_checked_at: null,
    setup_url: `https://example.test/${provider}`,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getAiSettings.mockResolvedValue({
    providers: [status('anthropic', true), status('openai', false), status('openrouter', false), status('xai', false)],
    roles: { research: null, writer: null },
    default: { provider: 'anthropic', model: MODEL, is_custom: false },
  })
  api.getAiModels.mockResolvedValue({
    provider: 'anthropic',
    source: 'cache',
    fetched_at: null,
    error: null,
    models: [{ id: MODEL, name: 'Claude Alpha' }],
  })
  api.getAiUsage.mockResolvedValue(usageReport())
  api.getAiUsageRecords.mockResolvedValue({ items: [], next_before: null })
  api.getAiUsagePolicy.mockResolvedValue(usagePolicy())
  api.getAiPricing.mockResolvedValue({ items: [] })
})

afterEach(cleanup)

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <AiSettings />
    </QueryClientProvider>,
  )
  return client
}

const sendButton = () =>
  within(screen.getByRole('dialog', { name: 'Send a test prompt?' })).getByRole('button', {
    name: 'Send test prompt',
  }) as HTMLButtonElement

describe('inference preview with real hooks (M4, M7)', () => {
  it('fetches the preview only when the dialog opens', async () => {
    api.getAiInferenceTestPreview.mockResolvedValue(inferencePreview())
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    const open = await within(section).findByRole('button', { name: 'Send test prompt…' })
    expect(api.getAiInferenceTestPreview).not.toHaveBeenCalled()

    fireEvent.click(open)
    await waitFor(() => expect(api.getAiInferenceTestPreview).toHaveBeenCalledWith('anthropic', MODEL))
    await waitFor(() => expect(sendButton().disabled).toBe(false))
  })

  it('does not enable confirm from a stale cached "allowed" preview while refetching on reopen', async () => {
    api.getAiInferenceTestPreview.mockResolvedValueOnce(inferencePreview())
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    const open = await within(section).findByRole('button', { name: 'Send test prompt…' })

    fireEvent.click(open)
    await waitFor(() => expect(sendButton().disabled).toBe(false))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))

    // Budget is exhausted meanwhile; hold the refetch in flight.
    const refetch = deferred<AiInferenceTestPreview>()
    api.getAiInferenceTestPreview.mockReturnValueOnce(refetch.promise)
    fireEvent.click(open)
    await waitFor(() => expect(api.getAiInferenceTestPreview).toHaveBeenCalledTimes(2))
    expect(sendButton().disabled).toBe(true)
    fireEvent.click(sendButton())
    expect(api.runAiInferenceTest).not.toHaveBeenCalled()

    refetch.resolve(inferencePreview({ policy_decision: 'over_budget' }))
    expect(await screen.findByText(/exceed the configured monthly budget/)).toBeTruthy()
    expect(sendButton().disabled).toBe(true)
  })
})

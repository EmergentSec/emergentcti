import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, type AxiosResponse } from 'axios'
import { AiSettings } from './AiSettings'
import * as aiApi from '@/api/ai'
import { AI_ERROR_MESSAGES } from '@/lib/aiErrors'
import type { AiModelList, AiProviderStatus, AiSettings as AiSettingsData } from '@/types/ai'
import * as AiSettingsModule from './AiSettings'
import { inferencePreview } from '@/test/fixtures/ai'

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
}))

const mockPreview = vi.fn()
vi.mock('@/hooks/useAiUsage', () => ({
  useAiUsage: () => ({ data: undefined, isLoading: true, error: null }),
  useAiUsageRecords: () => ({ data: undefined, isLoading: true, error: null }),
  useAiUsagePolicy: () => ({ data: undefined, isLoading: true, error: null }),
  useSaveAiUsagePolicy: () => ({ mutate: vi.fn(), isPending: false }),
  useAiPricing: () => ({ data: { items: [] }, isLoading: false, error: null }),
  useSaveAiPricingRow: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteAiPricingRow: () => ({ mutate: vi.fn(), isPending: false }),
  useAiInferenceTestPreview: (...args: unknown[]) => mockPreview(...args),
  invalidateAiSpendQueries: vi.fn(),
}))

const mockToast = vi.fn()
vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

const api = vi.mocked(aiApi)
const FAKE_KEY = 'sk-test-not-a-real-key-0000'

function provider(p: AiProviderStatus['provider'], name: string, extra: Partial<AiProviderStatus> = {}): AiProviderStatus {
  return {
    provider: p,
    display_name: name,
    configured: false,
    key_hint: null,
    models_fetched_at: null,
    last_check_status: null,
    last_check_category: null,
    last_checked_at: null,
    setup_url: `https://example.test/${p}/keys`,
    ...extra,
  }
}

function settings(overrides: Partial<AiSettingsData> = {}): AiSettingsData {
  return {
    providers: [
      provider('anthropic', 'Anthropic', { configured: true, key_hint: 'a1b2' }),
      provider('openai', 'OpenAI'),
      provider('openrouter', 'OpenRouter'),
      provider('xai', 'xAI (Grok)'),
    ],
    default: null,
    roles: { research: null, writer: null },
    ...overrides,
  }
}

const MODELS: AiModelList = {
  provider: 'anthropic',
  source: 'live',
  fetched_at: new Date().toISOString(),
  error: null,
  models: [
    { id: 'claude-alpha-20260101', name: 'Claude Alpha' },
    { id: 'claude-beta-20260201', name: 'Claude Beta' },
  ],
}

function httpError(status: number, data: unknown) {
  return new AxiosError('Request failed', String(status), undefined, undefined, { status, data } as AxiosResponse)
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const result = render(
    <QueryClientProvider client={client}>
      <AiSettings />
    </QueryClientProvider>,
  )
  return { ...result, client }
}

/** A promise the test settles by hand, to hold a request in flight. */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

function button(scope: HTMLElement, name: string | RegExp) {
  return within(scope).getByRole('button', { name }) as HTMLButtonElement
}

function card(name: string) {
  return screen.getByRole('region', { name })
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getAiSettings.mockResolvedValue(settings())
  api.getAiModels.mockResolvedValue(MODELS)
  mockPreview.mockReturnValue({ data: inferencePreview(), isLoading: false, isFetching: false, error: null })
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
})

describe('AiSettings', () => {
  it('discloses that providers are external paid services and nothing is sent automatically', async () => {
    renderPage()
    expect(screen.getByText('AI providers are external, paid services')).toBeTruthy()
    expect(
      screen.getByText(/research and report writing send only the prompts you\s+explicitly start/i),
    ).toBeTruthy()
    await screen.findByRole('region', { name: 'Anthropic' })
  })

  it('renders one card per provider with configured state and the masked hint only', async () => {
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })
    expect(within(anthropic).getByText('Configured')).toBeTruthy()
    expect(within(anthropic).getByText('••••a1b2')).toBeTruthy()
    for (const name of ['OpenAI', 'OpenRouter', 'xAI (Grok)']) {
      expect(within(card(name)).getByText('Not configured')).toBeTruthy()
      expect(within(card(name)).queryByRole('button', { name: 'Check connection' })).toBeNull()
    }
    const link = within(anthropic).getByRole('link', { name: /Get an API key/ })
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('saves a key, clears the input, and never renders or stores the key', async () => {
    api.putAiProviderKey.mockResolvedValue(provider('openai', 'OpenAI', { configured: true, key_hint: '0000' }))
    const { client } = renderPage()
    const openai = await screen.findByRole('region', { name: 'OpenAI' })
    const input = within(openai).getByLabelText('OpenAI API key') as HTMLInputElement
    expect(input.type).toBe('password')
    expect(input.getAttribute('autocomplete')).toBe('off')

    fireEvent.change(input, { target: { value: `  ${FAKE_KEY} ` } })
    fireEvent.click(within(openai).getByRole('button', { name: 'Save key' }))

    await waitFor(() => expect(api.putAiProviderKey).toHaveBeenCalledWith('openai', FAKE_KEY))
    await waitFor(() => expect(input.value).toBe(''))
    expect(mockToast).toHaveBeenCalledWith('OpenAI key saved', 'success')
    expect(document.body.innerHTML).not.toContain(FAKE_KEY)
    expect(JSON.stringify(mockToast.mock.calls)).not.toContain(FAKE_KEY)
    expect(JSON.stringify({ ...localStorage })).not.toContain(FAKE_KEY)
    expect(JSON.stringify({ ...sessionStorage })).not.toContain(FAKE_KEY)
    expect(window.location.href).not.toContain(FAKE_KEY)
    // Settings are refetched so the card picks up the new configured state.
    await waitFor(() => expect(api.getAiSettings).toHaveBeenCalledTimes(2))
    // The settled save (whose variables held the key) is gone from TanStack state.
    await waitFor(() => expect(client.getMutationCache().getAll()).toHaveLength(0))
  })

  it('shows a mapped error and keeps the input when saving fails', async () => {
    api.putAiProviderKey.mockRejectedValue(httpError(422, { detail: 'API key must be 1-512 characters' }))
    renderPage()
    const openai = await screen.findByRole('region', { name: 'OpenAI' })
    const input = within(openai).getByLabelText('OpenAI API key') as HTMLInputElement
    fireEvent.change(input, { target: { value: FAKE_KEY } })
    fireEvent.click(within(openai).getByRole('button', { name: 'Save key' }))
    expect(await within(openai).findByText('API key must be 1-512 characters')).toBeTruthy()
    expect(input.value).toBe(FAKE_KEY)
  })

  it('asks for confirmation before removing a key', async () => {
    api.deleteAiProvider.mockResolvedValue(undefined)
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })
    fireEvent.click(within(anthropic).getByRole('button', { name: 'Remove key' }))

    const dialog = screen.getByRole('dialog', { name: 'Remove Anthropic key?' })
    expect(within(dialog).getByText(/Nothing falls back to another provider/)).toBeTruthy()
    expect(api.deleteAiProvider).not.toHaveBeenCalled()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(api.deleteAiProvider).not.toHaveBeenCalled()

    fireEvent.click(within(anthropic).getByRole('button', { name: 'Remove key' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove key' }))
    await waitFor(() => expect(api.deleteAiProvider).toHaveBeenCalledWith('anthropic'))
    expect(mockToast).toHaveBeenCalledWith('Anthropic key removed', 'success')
  })

  it('describes the connection check as free and renders a success result', async () => {
    api.checkAiProvider.mockResolvedValue({ ok: true, error: null, checked_at: new Date().toISOString() })
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })
    expect(within(anthropic).getByText(/free: it verifies the key without running a model/)).toBeTruthy()
    expect(within(anthropic).getByText('Connection not checked yet.')).toBeTruthy()
    fireEvent.click(within(anthropic).getByRole('button', { name: 'Check connection' }))
    expect(await within(anthropic).findByText('Connection OK. The key works.')).toBeTruthy()
    expect(api.checkAiProvider).toHaveBeenCalledWith('anthropic')
  })

  it('renders a failed check as a mapped category message, not the raw provider message', async () => {
    api.checkAiProvider.mockResolvedValue({
      ok: false,
      error: { category: 'invalid_credentials', message: 'RAW provider body 401' },
      checked_at: new Date().toISOString(),
    })
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })
    fireEvent.click(within(anthropic).getByRole('button', { name: 'Check connection' }))
    expect(await within(anthropic).findByText(AI_ERROR_MESSAGES.invalid_credentials)).toBeTruthy()
    expect(screen.queryByText(/RAW provider body/)).toBeNull()
  })

  it('shows the persisted last check status', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({
        providers: [
          provider('anthropic', 'Anthropic', {
            configured: true,
            key_hint: 'a1b2',
            last_check_status: 'error',
            last_check_category: 'insufficient_quota',
            last_checked_at: new Date().toISOString(),
          }),
          provider('openai', 'OpenAI'),
          provider('openrouter', 'OpenRouter'),
          provider('xai', 'xAI (Grok)'),
        ],
      }),
    )
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })
    expect(within(anthropic).getByText(new RegExp(AI_ERROR_MESSAGES.insufficient_quota.replace(/[.]/g, '\\.')))).toBeTruthy()
  })

  it('refreshes models with refresh=true and shows the source', async () => {
    api.getAiModels.mockImplementation(async (_p, refresh) =>
      refresh ? MODELS : { ...MODELS, source: 'fallback', fetched_at: null },
    )
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })
    fireEvent.click(within(anthropic).getByRole('button', { name: 'Refresh models' }))
    expect(await within(anthropic).findByText(/2 models available/)).toBeTruthy()
    expect(within(anthropic).getByText('Live')).toBeTruthy()
    expect(api.getAiModels).toHaveBeenCalledWith('anthropic', true)
  })

  it('shows an explicit unconfigured default state', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ providers: settings().providers.map((p) => ({ ...p, configured: false, key_hint: null })) }),
    )
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    expect(within(section).getByText('No default model.')).toBeTruthy()
    expect(within(section).getByText(/Nothing falls back to another provider/)).toBeTruthy()
    expect(within(section).getByText('Save a provider key above to choose a default model.')).toBeTruthy()
    expect(api.getAiModels).not.toHaveBeenCalled()
  })

  it('saves a listed default model', async () => {
    api.putAiDefault.mockResolvedValue({ provider: 'anthropic', model: 'claude-beta-20260201', is_custom: false })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    await within(section).findByText('Live')
    fireEvent.click(within(section).getByRole('button', { name: /Model/ }))
    fireEvent.click(screen.getByRole('option', { name: /Claude Beta/ }))
    fireEvent.click(within(section).getByRole('button', { name: 'Save default' }))
    await waitFor(() =>
      expect(api.putAiDefault).toHaveBeenCalledWith({ provider: 'anthropic', model: 'claude-beta-20260201', is_custom: false }),
    )
  })

  it('saves a custom model ID exactly as typed', async () => {
    api.putAiDefault.mockResolvedValue({ provider: 'anthropic', model: ' Acme/My-Model V2', is_custom: true })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    await within(section).findByText('Live')
    fireEvent.click(within(section).getByRole('button', { name: /Model/ }))
    fireEvent.click(screen.getByRole('option', { name: /Use custom model ID…/ }))
    fireEvent.change(within(section).getByLabelText('Custom model ID'), { target: { value: ' Acme/My-Model V2' } })
    fireEvent.click(within(section).getByRole('button', { name: 'Save default' }))
    await waitFor(() =>
      expect(api.putAiDefault).toHaveBeenCalledWith({ provider: 'anthropic', model: ' Acme/My-Model V2', is_custom: true }),
    )
  })

  it('keeps the saved default visible when model discovery fails', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    api.getAiModels.mockRejectedValue(httpError(504, { detail: { category: 'timeout', message: 'raw' } }))
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    expect(await within(section).findByText(new RegExp(AI_ERROR_MESSAGES.timeout.replace(/[.]/g, '\\.')))).toBeTruthy()
    expect(within(section).getByRole('button', { name: /claude-alpha-20260101/ })).toBeTruthy()
    expect(within(section).getByText(/Current default:/)).toBeTruthy()
    expect(api.putAiDefault).not.toHaveBeenCalled()
    expect(api.deleteAiDefault).not.toHaveBeenCalled()
  })

  it('clears the default to an explicit unconfigured state', async () => {
    api.getAiSettings.mockResolvedValueOnce(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    api.deleteAiDefault.mockResolvedValue(undefined)
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    fireEvent.click(await within(section).findByRole('button', { name: 'Clear default' }))
    await waitFor(() => expect(api.deleteAiDefault).toHaveBeenCalled())
    expect(await within(section).findByText('No default model.')).toBeTruthy()
  })

  it('runs the billable inference test only after explicit confirmation', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    api.runAiInferenceTest.mockResolvedValue({
      ok: true,
      error: null,
      latency_ms: 321,
      usage: {
        record_id: 'rec-1',
        input_tokens: 5,
        output_tokens: 1,
        usage_source: 'provider_reported',
        cost_usd: '0.0001',
        cost_source: 'estimated',
      },
    })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    const open = await within(section).findByRole('button', { name: 'Send test prompt…' })

    fireEvent.click(open)
    let dialog = screen.getByRole('dialog', { name: 'Send a test prompt?' })
    expect(within(dialog).getByText(/may charge for this request/)).toBeTruthy()
    expect(within(dialog).getByText('Reply with the single word: OK')).toBeTruthy()
    // M3: provider, host and model are all shown once the preview has loaded.
    expect(within(dialog).getByText('Sent to Anthropic (api.anthropic.com)')).toBeTruthy()
    expect(within(dialog).getByText('claude-alpha-20260101')).toBeTruthy()
    expect(within(dialog).getByText(/^Provider:/).textContent).toBe('Provider: Anthropic')
    expect(api.runAiInferenceTest).not.toHaveBeenCalled()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(api.runAiInferenceTest).not.toHaveBeenCalled()

    fireEvent.click(open)
    dialog = screen.getByRole('dialog', { name: 'Send a test prompt?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Send test prompt' }))
    await waitFor(() => expect(api.runAiInferenceTest).toHaveBeenCalledTimes(1))
    expect(api.runAiInferenceTest).toHaveBeenCalledWith('anthropic', 'claude-alpha-20260101')
    expect(await within(section).findByText(/replied in 321 ms/)).toBeTruthy()
    expect(within(section).getByText(/\$0\.0001 est\./)).toBeTruthy()
  })

  it('disables inference confirm when preview policy blocks the request', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    mockPreview.mockReturnValue({
      data: inferencePreview({ pricing_known: false, estimated_max_cost_usd: null, policy_decision: 'blocked_unpriced' }),
      isLoading: false,
      isFetching: false,
      error: null,
    })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    fireEvent.click(await within(section).findByRole('button', { name: 'Send test prompt…' }))
    const dialog = screen.getByRole('dialog', { name: 'Send a test prompt?' })
    const send = within(dialog).getByRole('button', { name: 'Send test prompt' }) as HTMLButtonElement
    expect(send.disabled).toBe(true)
    expect(within(dialog).getByText(/no local pricing row/)).toBeTruthy()
  })

  it('disables inference confirm when the preview says over budget', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    mockPreview.mockReturnValue({
      data: inferencePreview({ policy_decision: 'over_budget' }),
      isLoading: false,
      isFetching: false,
      error: null,
    })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    fireEvent.click(await within(section).findByRole('button', { name: 'Send test prompt…' }))
    const dialog = screen.getByRole('dialog', { name: 'Send a test prompt?' })
    expect(button(dialog, 'Send test prompt').disabled).toBe(true)
    expect(within(dialog).getByText(/exceed the configured monthly budget/)).toBeTruthy()
  })

  it('shows the preview error and keeps confirm disabled', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    mockPreview.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: httpError(503, { detail: { category: 'not_configured', message: 'raw' } }),
    })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    fireEvent.click(await within(section).findByRole('button', { name: 'Send test prompt…' }))
    const dialog = screen.getByRole('dialog', { name: 'Send a test prompt?' })
    expect(within(dialog).getByText(AI_ERROR_MESSAGES.not_configured)).toBeTruthy()
    expect(button(dialog, 'Send test prompt').disabled).toBe(true)
  })

  it('keeps confirm disabled while a cached preview is being refetched (M4)', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    mockPreview.mockReturnValue({ data: inferencePreview(), isLoading: false, isFetching: true, error: null })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    fireEvent.click(await within(section).findByRole('button', { name: 'Send test prompt…' }))
    const dialog = screen.getByRole('dialog', { name: 'Send a test prompt?' })
    expect(button(dialog, 'Send test prompt').disabled).toBe(true)
    expect(within(dialog).getByText('Rechecking budget and policy…')).toBeTruthy()
  })

  it('no longer exports a hard-coded inference prompt (L6)', () => {
    expect('INFERENCE_TEST_PROMPT' in AiSettingsModule).toBe(false)
  })

  it('maps a failed inference test to a category message', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    api.runAiInferenceTest.mockResolvedValue({
      ok: false,
      error: { category: 'model_unavailable', message: 'raw' },
      latency_ms: null,
      usage: null,
    })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    fireEvent.click(await within(section).findByRole('button', { name: 'Send test prompt…' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Send test prompt' }))
    expect(await within(section).findByText(AI_ERROR_MESSAGES.model_unavailable)).toBeTruthy()
  })
})

describe('AiSettings conflicting writes', () => {
  it('blocks removing a key while a key save is in flight, including from an open confirm dialog', async () => {
    const put = deferred<AiProviderStatus>()
    api.putAiProviderKey.mockReturnValue(put.promise)
    api.deleteAiProvider.mockResolvedValue(undefined)
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })

    // Dialog already open when the save starts.
    fireEvent.click(button(anthropic, 'Remove key'))
    const dialog = screen.getByRole('dialog', { name: 'Remove Anthropic key?' })
    fireEvent.change(within(anthropic).getByLabelText('Replace Anthropic API key'), { target: { value: FAKE_KEY } })
    fireEvent.submit(within(anthropic).getByLabelText('Replace Anthropic API key').closest('form')!)
    await waitFor(() => expect(api.putAiProviderKey).toHaveBeenCalledTimes(1))

    const confirm = button(dialog, 'Remove key')
    await waitFor(() => expect(confirm.disabled).toBe(true))
    fireEvent.click(confirm)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(button(anthropic, 'Remove key').disabled).toBe(true)
    fireEvent.click(button(anthropic, 'Remove key'))
    expect(api.deleteAiProvider).not.toHaveBeenCalled()

    put.resolve(provider('anthropic', 'Anthropic', { configured: true, key_hint: '0000' }))
    await waitFor(() => expect(button(anthropic, 'Remove key').disabled).toBe(false))
    fireEvent.click(button(anthropic, 'Remove key'))
    fireEvent.click(button(screen.getByRole('dialog'), 'Remove key'))
    await waitFor(() => expect(api.deleteAiProvider).toHaveBeenCalledTimes(1))
  })

  it('blocks saving a key while a key removal is in flight', async () => {
    const del = deferred<void>()
    api.deleteAiProvider.mockReturnValue(del.promise)
    api.putAiProviderKey.mockResolvedValue(provider('anthropic', 'Anthropic', { configured: true, key_hint: '0000' }))
    renderPage()
    const anthropic = await screen.findByRole('region', { name: 'Anthropic' })
    const input = within(anthropic).getByLabelText('Replace Anthropic API key')
    fireEvent.change(input, { target: { value: FAKE_KEY } })

    fireEvent.click(button(anthropic, 'Remove key'))
    fireEvent.click(button(screen.getByRole('dialog'), 'Remove key'))
    await waitFor(() => expect(api.deleteAiProvider).toHaveBeenCalledTimes(1))

    await waitFor(() => expect(button(anthropic, 'Replace key').disabled).toBe(true))
    fireEvent.click(button(anthropic, 'Replace key'))
    fireEvent.submit(input.closest('form')!)
    expect(api.putAiProviderKey).not.toHaveBeenCalled()

    del.resolve()
    await waitFor(() => expect(button(anthropic, 'Replace key').disabled).toBe(false))
    fireEvent.click(button(anthropic, 'Replace key'))
    await waitFor(() => expect(api.putAiProviderKey).toHaveBeenCalledTimes(1))
  })

  it('blocks clearing the default while a default save is in flight', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    const put = deferred<{ provider: 'anthropic'; model: string; is_custom: boolean }>()
    api.putAiDefault.mockReturnValue(put.promise)
    api.deleteAiDefault.mockResolvedValue(undefined)
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    await within(section).findByText('Live')
    fireEvent.click(within(section).getByRole('button', { name: /^Model/ }))
    fireEvent.click(screen.getByRole('option', { name: /Claude Beta/ }))
    fireEvent.click(button(section, 'Save default'))
    await waitFor(() => expect(api.putAiDefault).toHaveBeenCalledTimes(1))

    await waitFor(() => expect(button(section, 'Clear default').disabled).toBe(true))
    fireEvent.click(button(section, 'Clear default'))
    expect(api.deleteAiDefault).not.toHaveBeenCalled()

    put.resolve({ provider: 'anthropic', model: 'claude-beta-20260201', is_custom: false })
    await waitFor(() => expect(button(section, 'Clear default').disabled).toBe(false))
    fireEvent.click(button(section, 'Clear default'))
    await waitFor(() => expect(api.deleteAiDefault).toHaveBeenCalledTimes(1))
  })

  it('blocks saving the default while a clear is in flight', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    const del = deferred<void>()
    api.deleteAiDefault.mockReturnValue(del.promise)
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    await within(section).findByText('Live')
    // An unsaved change, so Save would otherwise be enabled.
    fireEvent.click(within(section).getByRole('button', { name: /^Model/ }))
    fireEvent.click(screen.getByRole('option', { name: /Claude Beta/ }))
    expect(button(section, 'Save default').disabled).toBe(false)

    fireEvent.click(button(section, 'Clear default'))
    await waitFor(() => expect(api.deleteAiDefault).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(button(section, /^Sav/).disabled).toBe(true))
    fireEvent.click(button(section, /^Sav/))
    expect(api.putAiDefault).not.toHaveBeenCalled()

    del.resolve()
    await waitFor(() => expect(mockToast).toHaveBeenCalledWith('Default model cleared', 'success'))
    await waitFor(() => expect(button(section, 'Clear default').disabled).toBe(false))
    expect(api.putAiDefault).not.toHaveBeenCalled()
  })
})

describe('AiSettings default draft sync', () => {
  it('resets the draft model when the saved default is cleared elsewhere', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    const { client } = renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    await within(section).findByRole('button', { name: /claude-alpha-20260101/ })

    // Another admin clears the default; providers are unchanged.
    api.getAiSettings.mockResolvedValue(settings())
    await client.refetchQueries({ queryKey: ['ai-settings'] })

    expect(await within(section).findByText('No default model.')).toBeTruthy()
    await waitFor(() => expect(within(section).queryByRole('button', { name: /claude-alpha-20260101/ })).toBeNull())
    expect(within(section).getByRole('button', { name: /Select a model/ })).toBeTruthy()
    expect(button(section, 'Save default').disabled).toBe(true)
    expect((within(section).getByLabelText('Provider') as HTMLSelectElement).value).toBe('anthropic')
    expect(api.putAiDefault).not.toHaveBeenCalled()
  })

  it('keeps an unsaved draft across refetches that leave the default unchanged', async () => {
    const { client } = renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    await within(section).findByText('Live')
    fireEvent.click(within(section).getByRole('button', { name: /^Model/ }))
    fireEvent.click(screen.getByRole('option', { name: /Claude Beta/ }))

    await client.refetchQueries({ queryKey: ['ai-settings'] })
    await waitFor(() => expect(api.getAiSettings).toHaveBeenCalledTimes(2))

    expect(within(section).getByRole('button', { name: /claude-beta-20260201/ })).toBeTruthy()
    expect(button(section, 'Save default').disabled).toBe(false)
  })
})

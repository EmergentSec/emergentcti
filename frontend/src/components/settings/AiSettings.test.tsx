import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, type AxiosResponse } from 'axios'
import { AiSettings } from './AiSettings'
import * as aiApi from '@/api/ai'
import { AI_ERROR_MESSAGES } from '@/lib/aiErrors'
import type { AiModelList, AiProviderStatus, AiSettings as AiSettingsData } from '@/types/ai'

vi.mock('@/api/ai', () => ({
  getAiSettings: vi.fn(),
  putAiProviderKey: vi.fn(),
  deleteAiProvider: vi.fn(),
  checkAiProvider: vi.fn(),
  getAiModels: vi.fn(),
  runAiInferenceTest: vi.fn(),
  putAiDefault: vi.fn(),
  deleteAiDefault: vi.fn(),
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
  return render(
    <QueryClientProvider client={client}>
      <AiSettings />
    </QueryClientProvider>,
  )
}

function card(name: string) {
  return screen.getByRole('region', { name })
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getAiSettings.mockResolvedValue(settings())
  api.getAiModels.mockResolvedValue(MODELS)
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
    expect(screen.getByText(/Nothing is sent to a provider until a future feature asks you to/)).toBeTruthy()
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
    renderPage()
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
    api.runAiInferenceTest.mockResolvedValue({ ok: true, error: null, latency_ms: 321 })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    const open = await within(section).findByRole('button', { name: 'Send test prompt…' })

    fireEvent.click(open)
    let dialog = screen.getByRole('dialog', { name: 'Send a test prompt?' })
    expect(within(dialog).getByText(/may charge for this request/)).toBeTruthy()
    expect(within(dialog).getByText('Reply with the single word: OK')).toBeTruthy()
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
  })

  it('maps a failed inference test to a category message', async () => {
    api.getAiSettings.mockResolvedValue(
      settings({ default: { provider: 'anthropic', model: 'claude-alpha-20260101', is_custom: false } }),
    )
    api.runAiInferenceTest.mockResolvedValue({
      ok: false,
      error: { category: 'model_unavailable', message: 'raw' },
      latency_ms: null,
    })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Default model' })
    fireEvent.click(await within(section).findByRole('button', { name: 'Send test prompt…' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Send test prompt' }))
    expect(await within(section).findByText(AI_ERROR_MESSAGES.model_unavailable)).toBeTruthy()
  })
})

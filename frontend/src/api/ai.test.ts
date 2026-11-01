import { afterEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import api from './client'
import {
  checkAiProvider,
  deleteAiDefault,
  deleteAiProvider,
  getAiModels,
  getAiSettings,
  putAiDefault,
  putAiProviderKey,
  runAiInferenceTest,
} from './ai'
import { aiErrorFromResponse, aiRequestErrorMessage, AI_ERROR_MESSAGES, describeAiCategory } from '@/lib/aiErrors'

afterEach(() => vi.restoreAllMocks())

describe('AI settings API', () => {
  it('uses the contract routes', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: {} })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })
    const put = vi.spyOn(api, 'put').mockResolvedValue({ data: {} })
    const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: undefined })

    await getAiSettings()
    expect(get).toHaveBeenCalledWith('/settings/ai')

    await putAiProviderKey('openai', 'sk-test-not-a-real-key-0000')
    expect(put).toHaveBeenCalledWith('/settings/ai/providers/openai', { api_key: 'sk-test-not-a-real-key-0000' })

    await deleteAiProvider('xai')
    expect(del).toHaveBeenCalledWith('/settings/ai/providers/xai')

    await checkAiProvider('anthropic')
    expect(post).toHaveBeenCalledWith('/settings/ai/providers/anthropic/check')

    await getAiModels('openrouter')
    expect(get).toHaveBeenLastCalledWith('/settings/ai/providers/openrouter/models', { params: { refresh: false } })

    await getAiModels('openrouter', true)
    expect(get).toHaveBeenLastCalledWith('/settings/ai/providers/openrouter/models', { params: { refresh: true } })

    const dflt = { provider: 'anthropic' as const, model: ' My Model ', is_custom: true }
    await putAiDefault(dflt)
    expect(put).toHaveBeenLastCalledWith('/settings/ai/default', dflt)

    await deleteAiDefault()
    expect(del).toHaveBeenLastCalledWith('/settings/ai/default')
  })

  it('sends the inference test with confirm: true', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { ok: true, error: null, latency_ms: 10 } })
    await runAiInferenceTest('openai', 'gpt-x')
    expect(post).toHaveBeenCalledWith('/settings/ai/providers/openai/inference-test', { model: 'gpt-x', confirm: true })
  })
})

function httpError(status: number, data: unknown) {
  return new AxiosError('Request failed', String(status), undefined, undefined, { status, data } as AxiosResponse)
}

describe('AI error mapping', () => {
  it('reads the category from a FastAPI detail wrapper or a bare body', () => {
    const wrapped = httpError(409, { detail: { category: 'not_configured', message: 'x' } })
    const bare = httpError(409, { category: 'not_configured', message: 'x' })
    expect(aiErrorFromResponse(wrapped)?.category).toBe('not_configured')
    expect(aiErrorFromResponse(bare)?.category).toBe('not_configured')
    expect(aiErrorFromResponse(new Error('boom'))).toBeNull()
  })

  it('maps categories to fixed copy and never echoes the backend message', () => {
    const err = httpError(409, { detail: { category: 'invalid_credentials', message: 'RAW provider text' } })
    expect(aiRequestErrorMessage(err, 'fallback')).toBe(AI_ERROR_MESSAGES.invalid_credentials)
  })

  it('falls back for plain API errors and unknown categories', () => {
    expect(aiRequestErrorMessage(httpError(422, { detail: 'Pick a listed model' }), 'fallback')).toBe('Pick a listed model')
    expect(aiRequestErrorMessage(new Error('boom'), 'fallback')).toBe('fallback')
    expect(describeAiCategory('something_new')).toMatch(/went wrong/)
    expect(describeAiCategory(null)).toMatch(/went wrong/)
  })
})

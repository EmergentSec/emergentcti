import api from './client'
import type {
  AiCheckResult,
  AiDefault,
  AiInferenceResult,
  AiModelList,
  AiProvider,
  AiProviderStatus,
  AiSettings,
} from '@/types/ai'

const BASE = '/settings/ai'

export async function getAiSettings(): Promise<AiSettings> {
  const { data } = await api.get<AiSettings>(BASE)
  return data
}

/** Create or replace a provider key. The backend makes no network call. */
export async function putAiProviderKey(provider: AiProvider, apiKey: string): Promise<AiProviderStatus> {
  const { data } = await api.put<AiProviderStatus>(`${BASE}/providers/${provider}`, { api_key: apiKey })
  return data
}

export async function deleteAiProvider(provider: AiProvider): Promise<void> {
  await api.delete(`${BASE}/providers/${provider}`)
}

/** Non-billable credential/connection check; never runs inference. */
export async function checkAiProvider(provider: AiProvider): Promise<AiCheckResult> {
  const { data } = await api.post<AiCheckResult>(`${BASE}/providers/${provider}/check`)
  return data
}

export async function getAiModels(provider: AiProvider, refresh = false): Promise<AiModelList> {
  const { data } = await api.get<AiModelList>(`${BASE}/providers/${provider}/models`, {
    params: { refresh },
  })
  return data
}

/**
 * Billable: sends one tiny fixed prompt to `model`. Call only from an explicit
 * user confirmation; the backend rejects anything but `confirm: true`.
 */
export async function runAiInferenceTest(provider: AiProvider, model: string): Promise<AiInferenceResult> {
  const { data } = await api.post<AiInferenceResult>(`${BASE}/providers/${provider}/inference-test`, {
    model,
    confirm: true,
  })
  return data
}

export async function putAiDefault(payload: AiDefault): Promise<AiDefault> {
  const { data } = await api.put<AiDefault>(`${BASE}/default`, payload)
  return data
}

export async function deleteAiDefault(): Promise<void> {
  await api.delete(`${BASE}/default`)
}

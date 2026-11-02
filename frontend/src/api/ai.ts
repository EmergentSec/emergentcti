import api from './client'
import type {
  AiCheckResult,
  AiDefault,
  AiInferenceResult,
  AiInferenceTestPreview,
  AiModelList,
  AiModelPricingRow,
  AiPricingList,
  AiProvider,
  AiProviderStatus,
  AiSettings,
  AiUsagePolicy,
  AiUsageRecordsResponse,
  AiUsageResponse,
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
export async function runAiInferenceTest(
  provider: AiProvider,
  model: string,
  retryOf?: string,
): Promise<AiInferenceResult> {
  const { data } = await api.post<AiInferenceResult>(`${BASE}/providers/${provider}/inference-test`, {
    model,
    confirm: true,
    ...(retryOf ? { retry_of: retryOf } : {}),
  })
  return data
}

export async function getAiInferenceTestPreview(provider: AiProvider, model: string): Promise<AiInferenceTestPreview> {
  const { data } = await api.get<AiInferenceTestPreview>(`${BASE}/providers/${provider}/inference-test/preview`, {
    params: { model },
  })
  return data
}

export async function getAiUsage(month?: string): Promise<AiUsageResponse> {
  const { data } = await api.get<AiUsageResponse>(`${BASE}/usage`, { params: month ? { month } : undefined })
  return data
}

export async function getAiUsageRecords(
  month?: string,
  limit = 50,
  before?: string,
): Promise<AiUsageRecordsResponse> {
  const { data } = await api.get<AiUsageRecordsResponse>(`${BASE}/usage/records`, {
    params: { month, limit, before },
  })
  return data
}

export async function getAiUsagePolicy(): Promise<AiUsagePolicy> {
  const { data } = await api.get<AiUsagePolicy>(`${BASE}/usage-policy`)
  return data
}

export async function putAiUsagePolicy(body: Omit<AiUsagePolicy, 'updated_at' | 'guarantee'>): Promise<AiUsagePolicy> {
  const { data } = await api.put<AiUsagePolicy>(`${BASE}/usage-policy`, body)
  return data
}

export async function getAiPricing(): Promise<AiPricingList> {
  const { data } = await api.get<AiPricingList>(`${BASE}/pricing`)
  return data
}

export async function putAiPricingRow(
  provider: AiProvider,
  model: string,
  payload: { input_usd_per_mtok: string; output_usd_per_mtok: string },
): Promise<AiModelPricingRow> {
  const { data } = await api.put<AiModelPricingRow>(
    `${BASE}/pricing/${provider}/${encodeURIComponent(model)}`,
    payload,
  )
  return data
}

export async function deleteAiPricingRow(provider: AiProvider, model: string): Promise<void> {
  await api.delete(`${BASE}/pricing/${provider}/${encodeURIComponent(model)}`)
}

export async function putAiDefault(payload: AiDefault): Promise<AiDefault> {
  const { data } = await api.put<AiDefault>(`${BASE}/default`, payload)
  return data
}

export async function deleteAiDefault(): Promise<void> {
  await api.delete(`${BASE}/default`)
}

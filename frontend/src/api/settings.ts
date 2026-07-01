import api from './client'
import type { ApiKey, ApiKeyCreate, ApiKeyCreateResponse } from '@/types/auth'
import type { InstanceConfig } from '@/types/settings'

export async function getApiKeys(): Promise<ApiKey[]> {
  const { data } = await api.get<ApiKey[]>('/settings/api-keys')
  return data
}

export async function createApiKey(payload: ApiKeyCreate): Promise<ApiKeyCreateResponse> {
  const { data } = await api.post<ApiKeyCreateResponse>('/settings/api-keys', payload)
  return data
}

export async function revokeApiKey(id: string): Promise<void> {
  await api.delete(`/settings/api-keys/${id}`)
}

export async function getConfig(): Promise<InstanceConfig> {
  const { data } = await api.get<InstanceConfig>('/settings/config')
  return data
}

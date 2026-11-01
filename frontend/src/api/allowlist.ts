import api from './client'
import type { AllowlistEntry, AllowlistEntryCreate } from '@/types/allowlist'

export async function getAllowlist(): Promise<AllowlistEntry[]> {
  const { data } = await api.get<AllowlistEntry[]>('/allowlist')
  return data
}

export async function createAllowlistEntry(payload: AllowlistEntryCreate): Promise<AllowlistEntry> {
  const { data } = await api.post<AllowlistEntry>('/allowlist', payload)
  return data
}

export async function deleteAllowlistEntry(id: string): Promise<void> {
  await api.delete(`/allowlist/${id}`)
}

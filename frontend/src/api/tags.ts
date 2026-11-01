import api from './client'
import type { TagSummary } from '@/types/tag'

export async function getTags(q?: string): Promise<TagSummary[]> {
  const params = q?.trim() ? { q: q.trim() } : undefined
  const { data } = await api.get<TagSummary[]>('/tags', { params })
  return data
}

export async function createTag(name: string): Promise<TagSummary> {
  const { data } = await api.post<TagSummary>('/tags', { name })
  return data
}

export async function deleteTag(id: string): Promise<void> {
  await api.delete(`/tags/${id}`)
}

import api from './client'
import type { Feed, FeedCreate, FeedUpdate, FeedRun } from '@/types/feed'

export async function getFeeds(): Promise<Feed[]> {
  const { data } = await api.get<Feed[]>('/feeds')
  return data
}

export async function getFeed(id: string): Promise<Feed> {
  const { data } = await api.get<Feed>(`/feeds/${id}`)
  return data
}

export async function createFeed(payload: FeedCreate): Promise<Feed> {
  const { data } = await api.post<Feed>('/feeds', payload)
  return data
}

export async function updateFeed(id: string, payload: FeedUpdate): Promise<Feed> {
  const { data } = await api.put<Feed>(`/feeds/${id}`, payload)
  return data
}

export async function deleteFeed(id: string): Promise<void> {
  await api.delete(`/feeds/${id}`)
}

export async function triggerFeed(id: string): Promise<FeedRun> {
  const { data } = await api.post<FeedRun>(`/feeds/${id}/trigger`)
  return data
}

export async function getFeedRuns(id: string): Promise<FeedRun[]> {
  const { data } = await api.get<FeedRun[]>(`/feeds/${id}/runs`)
  return data
}

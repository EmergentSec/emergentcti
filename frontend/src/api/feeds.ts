import client from './client';
import type {
  FeedResponse,
  FeedCreateRequest,
  FeedUpdateRequest,
  FeedRunResponse,
  FeedTriggerResponse,
} from '@/types/feed';

export async function getFeeds(): Promise<FeedResponse[]> {
  const response = await client.get<FeedResponse[]>('/feeds');
  return response.data;
}

export async function getFeed(id: string): Promise<FeedResponse> {
  const response = await client.get<FeedResponse>(`/feeds/${id}`);
  return response.data;
}

export async function createFeed(
  data: FeedCreateRequest
): Promise<FeedResponse> {
  const response = await client.post<FeedResponse>('/feeds', data);
  return response.data;
}

export async function updateFeed(
  id: string,
  data: FeedUpdateRequest
): Promise<FeedResponse> {
  const response = await client.put<FeedResponse>(`/feeds/${id}`, data);
  return response.data;
}

export async function deleteFeed(id: string): Promise<void> {
  await client.delete(`/feeds/${id}`);
}

export async function triggerFeed(id: string): Promise<FeedTriggerResponse> {
  const response = await client.post<FeedTriggerResponse>(
    `/feeds/${id}/trigger`
  );
  return response.data;
}

export async function getFeedRuns(id: string): Promise<FeedRunResponse[]> {
  const response = await client.get<FeedRunResponse[]>(`/feeds/${id}/runs`);
  return response.data;
}

export async function bulkUpdateFeeds(
  ids: string[],
  updates: { enabled?: boolean }
): Promise<{ updated: number }> {
  const response = await client.patch<{ updated: number }>('/feeds/bulk', {
    ids,
    ...updates,
  });
  return response.data;
}

export async function bulkDeleteFeeds(ids: string[]): Promise<{ deleted: number }> {
  const response = await client.delete<{ deleted: number }>('/feeds/bulk', {
    data: { ids },
  });
  return response.data;
}

export async function bulkTriggerFeeds(ids: string[]): Promise<{ triggered: number }> {
  const response = await client.post<{ triggered: number }>('/feeds/bulk/trigger', {
    ids,
  });
  return response.data;
}

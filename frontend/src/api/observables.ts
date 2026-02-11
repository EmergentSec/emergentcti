import client from './client';
import type {
  ObservableResponse,
  ObservableCreateRequest,
  ObservableUpdateRequest,
  ObservableFilters,
  ObservableStats,
} from '@/types/observable';
import type { PaginatedResponse } from '@/types/api';

export async function getObservables(
  filters: ObservableFilters = {}
): Promise<PaginatedResponse<ObservableResponse>> {
  const params: Record<string, string | number> = {};
  if (filters.page) params.page = filters.page;
  if (filters.size) params.size = filters.size;
  if (filters.type) params.type = filters.type;
  if (filters.value) params.value = filters.value;
  if (filters.confidence_min !== undefined)
    params.confidence_min = filters.confidence_min;
  if (filters.tlp) params.tlp = filters.tlp;
  if (filters.feed_id) params.feed_id = filters.feed_id;
  if (filters.is_active) params.is_active = filters.is_active;

  const response = await client.get<PaginatedResponse<ObservableResponse>>(
    '/observables',
    { params }
  );
  return response.data;
}

export async function getObservable(id: string): Promise<ObservableResponse> {
  const response = await client.get<ObservableResponse>(`/observables/${id}`);
  return response.data;
}

export async function createObservable(
  data: ObservableCreateRequest
): Promise<ObservableResponse> {
  const response = await client.post<ObservableResponse>('/observables', data);
  return response.data;
}

export async function updateObservable(
  id: string,
  data: ObservableUpdateRequest
): Promise<ObservableResponse> {
  const response = await client.put<ObservableResponse>(
    `/observables/${id}`,
    data
  );
  return response.data;
}

export async function deleteObservable(id: string): Promise<void> {
  await client.delete(`/observables/${id}`);
}

export async function getObservableStats(): Promise<ObservableStats> {
  const response = await client.get<ObservableStats>('/observables/stats');
  return response.data;
}

export async function bulkUpdateObservables(
  ids: string[],
  updates: {
    tlp?: string;
    confidence_score?: number;
    tags?: string[];
    add_tags?: string[];
    category?: string;
  }
): Promise<{ updated: number }> {
  const response = await client.put<{ updated: number }>('/observables/bulk', {
    ids,
    ...updates,
  });
  return response.data;
}

export async function bulkDeleteObservables(ids: string[]): Promise<{ deleted: number }> {
  const response = await client.delete<{ deleted: number }>('/observables/bulk', {
    data: { ids },
  });
  return response.data;
}

export async function bulkEnrich(ids: string[]): Promise<{ dispatched: number }> {
  const response = await client.post<{ dispatched: number }>(
    '/observables/bulk/enrich',
    { ids }
  );
  return response.data;
}

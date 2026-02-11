import client from './client';
import type { SearchParams, SearchResponse } from '@/types/search';
import type { DashboardStats } from '@/types/api';

export async function searchObservables(
  params: SearchParams
): Promise<SearchResponse> {
  const queryParams: Record<string, string | number> = { q: params.q };
  if (params.type) queryParams.type = params.type;
  if (params.page) queryParams.page = params.page;
  if (params.size) queryParams.size = params.size;

  const response = await client.get<SearchResponse>('/search', {
    params: queryParams,
  });
  return response.data;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await client.get<DashboardStats>('/dashboard/stats');
  return response.data;
}

import client from './client';
import type {
  SavedSearchResponse,
  SavedSearchCreate,
  SavedSearchUpdate,
} from '@/types/saved_search';

export async function getSavedSearches(): Promise<SavedSearchResponse[]> {
  const response = await client.get<SavedSearchResponse[]>('/saved-searches');
  return response.data;
}

export async function createSavedSearch(
  data: SavedSearchCreate
): Promise<SavedSearchResponse> {
  const response = await client.post<SavedSearchResponse>(
    '/saved-searches',
    data
  );
  return response.data;
}

export async function updateSavedSearch(
  id: string,
  data: SavedSearchUpdate
): Promise<SavedSearchResponse> {
  const response = await client.put<SavedSearchResponse>(
    `/saved-searches/${id}`,
    data
  );
  return response.data;
}

export async function deleteSavedSearch(id: string): Promise<void> {
  await client.delete(`/saved-searches/${id}`);
}

export async function setDefaultSearch(
  id: string
): Promise<SavedSearchResponse> {
  const response = await client.post<SavedSearchResponse>(
    `/saved-searches/${id}/default`
  );
  return response.data;
}

import client from './client';
import type {
  ThreatActorResponse,
  ThreatActorCreateRequest,
  ThreatActorUpdateRequest,
  ThreatActorFilters,
  ThreatActorCampaign,
} from '@/types/threat_actor';
import type { PaginatedResponse } from '@/types/api';

export async function getThreatActors(
  filters: ThreatActorFilters = {}
): Promise<PaginatedResponse<ThreatActorResponse>> {
  const params: Record<string, string | number> = {};
  if (filters.page) params.page = filters.page;
  if (filters.size) params.size = filters.size;
  if (filters.name) params.name = filters.name;
  if (filters.country) params.country = filters.country;
  if (filters.motivation) params.motivation = filters.motivation;

  const response = await client.get<PaginatedResponse<ThreatActorResponse>>(
    '/threat-actors',
    { params }
  );
  return response.data;
}

export async function getThreatActor(id: string): Promise<ThreatActorResponse> {
  const response = await client.get<ThreatActorResponse>(`/threat-actors/${id}`);
  return response.data;
}

export async function createThreatActor(
  data: ThreatActorCreateRequest
): Promise<ThreatActorResponse> {
  const response = await client.post<ThreatActorResponse>('/threat-actors', data);
  return response.data;
}

export async function updateThreatActor(
  id: string,
  data: ThreatActorUpdateRequest
): Promise<ThreatActorResponse> {
  const response = await client.put<ThreatActorResponse>(
    `/threat-actors/${id}`,
    data
  );
  return response.data;
}

export async function deleteThreatActor(id: string): Promise<void> {
  await client.delete(`/threat-actors/${id}`);
}

export async function linkThreatActorObservable(
  actorId: string,
  observableId: string
): Promise<void> {
  await client.post(`/threat-actors/${actorId}/observables`, {
    observable_id: observableId,
  });
}

export async function unlinkThreatActorObservable(
  actorId: string,
  observableId: string
): Promise<void> {
  await client.delete(`/threat-actors/${actorId}/observables/${observableId}`);
}

export async function linkThreatActorTechnique(
  actorId: string,
  techniqueId: string
): Promise<void> {
  await client.post(`/threat-actors/${actorId}/techniques`, {
    technique_id: techniqueId,
  });
}

export async function unlinkThreatActorTechnique(
  actorId: string,
  techniqueId: string
): Promise<void> {
  await client.delete(`/threat-actors/${actorId}/techniques/${techniqueId}`);
}

export async function getThreatActorCampaigns(
  actorId: string
): Promise<ThreatActorCampaign[]> {
  const response = await client.get<ThreatActorCampaign[]>(
    `/threat-actors/${actorId}/campaigns`
  );
  return response.data;
}

export async function getThreatActorsForObservable(
  observableId: string
): Promise<ThreatActorResponse[]> {
  // Fetch all threat actors and filter client-side for those linked to this observable
  // Alternatively, we use the dedicated endpoint if available
  const response = await client.get<PaginatedResponse<ThreatActorResponse>>(
    '/threat-actors',
    { params: { size: 100 } }
  );
  return response.data.items.filter((actor) =>
    actor.observables.some((o) => o.id === observableId)
  );
}

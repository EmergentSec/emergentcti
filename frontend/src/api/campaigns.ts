import client from './client';
import type {
  CampaignResponse,
  CampaignCreateRequest,
  CampaignUpdateRequest,
  CampaignFilters,
  CampaignTimelineResponse,
} from '@/types/campaign';
import type { PaginatedResponse } from '@/types/api';

export async function getCampaigns(
  filters: CampaignFilters = {}
): Promise<PaginatedResponse<CampaignResponse>> {
  const params: Record<string, string | number> = {};
  if (filters.page) params.page = filters.page;
  if (filters.size) params.size = filters.size;
  if (filters.name) params.name = filters.name;
  if (filters.status) params.status = filters.status;
  if (filters.threat_actor_id) params.threat_actor_id = filters.threat_actor_id;

  const response = await client.get<PaginatedResponse<CampaignResponse>>(
    '/campaigns',
    { params }
  );
  return response.data;
}

export async function getCampaign(id: string): Promise<CampaignResponse> {
  const response = await client.get<CampaignResponse>(`/campaigns/${id}`);
  return response.data;
}

export async function createCampaign(
  data: CampaignCreateRequest
): Promise<CampaignResponse> {
  const response = await client.post<CampaignResponse>('/campaigns', data);
  return response.data;
}

export async function updateCampaign(
  id: string,
  data: CampaignUpdateRequest
): Promise<CampaignResponse> {
  const response = await client.put<CampaignResponse>(
    `/campaigns/${id}`,
    data
  );
  return response.data;
}

export async function deleteCampaign(id: string): Promise<void> {
  await client.delete(`/campaigns/${id}`);
}

export async function linkCampaignObservable(
  campaignId: string,
  observableId: string
): Promise<void> {
  await client.post(`/campaigns/${campaignId}/observables`, {
    observable_id: observableId,
  });
}

export async function unlinkCampaignObservable(
  campaignId: string,
  observableId: string
): Promise<void> {
  await client.delete(`/campaigns/${campaignId}/observables/${observableId}`);
}

export async function getCampaignTimeline(
  campaignId: string
): Promise<CampaignTimelineResponse> {
  const response = await client.get<CampaignTimelineResponse>(
    `/campaigns/${campaignId}/timeline`
  );
  return response.data;
}

export async function getCampaignsForObservable(
  observableId: string
): Promise<CampaignResponse[]> {
  const response = await client.get<PaginatedResponse<CampaignResponse>>(
    '/campaigns',
    { params: { size: 100 } }
  );
  return response.data.items.filter((campaign) =>
    campaign.observables.some((o) => o.id === observableId)
  );
}

import client from './client';
import type {
  ProviderInfo,
  EnrichmentConfigResponse,
  EnrichmentConfigUpdate,
  EnrichmentRunResponse,
} from '@/types/enrichment';

export async function getProviders(): Promise<ProviderInfo[]> {
  const { data } = await client.get<ProviderInfo[]>('/enrichment/providers');
  return data;
}

export async function getEnrichmentConfigs(): Promise<EnrichmentConfigResponse[]> {
  const { data } = await client.get<EnrichmentConfigResponse[]>('/enrichment/config');
  return data;
}

export async function updateEnrichmentConfig(
  name: string,
  update: EnrichmentConfigUpdate
): Promise<EnrichmentConfigResponse> {
  const { data } = await client.put<EnrichmentConfigResponse>(
    `/enrichment/config/${name}`,
    update
  );
  return data;
}

export async function triggerEnrichment(
  observableId: string,
  providerName?: string
): Promise<EnrichmentRunResponse> {
  const body = providerName ? { provider_name: providerName } : {};
  const { data } = await client.post<EnrichmentRunResponse>(
    `/observables/${observableId}/enrich`,
    body
  );
  return data;
}

export async function getEnrichmentHistory(
  observableId: string
): Promise<EnrichmentRunResponse[]> {
  const { data } = await client.get<EnrichmentRunResponse[]>(
    `/observables/${observableId}/enrichments`
  );
  return data;
}

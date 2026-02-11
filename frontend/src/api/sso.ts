import client from './client';
import type {
  SSOProviderPublic,
  SSOProviderResponse,
  SSOProviderConfigUpdate,
  SSOAuthorizeResponse,
} from '@/types/sso';

export async function getSSOProviders(): Promise<SSOProviderPublic[]> {
  const { data } = await client.get<SSOProviderPublic[]>('/sso/providers');
  return data;
}

export async function getSSOAuthorizeUrl(
  providerType: string
): Promise<SSOAuthorizeResponse> {
  const { data } = await client.get<SSOAuthorizeResponse>(
    `/sso/${providerType}/authorize`
  );
  return data;
}

export async function getSSOConfigs(): Promise<SSOProviderResponse[]> {
  const { data } = await client.get<SSOProviderResponse[]>('/sso/config');
  return data;
}

export async function updateSSOConfig(
  providerType: string,
  config: SSOProviderConfigUpdate
): Promise<SSOProviderResponse> {
  const { data } = await client.put<SSOProviderResponse>(
    `/sso/config/${providerType}`,
    config
  );
  return data;
}

export async function deleteSSOConfig(providerType: string): Promise<void> {
  await client.delete(`/sso/config/${providerType}`);
}

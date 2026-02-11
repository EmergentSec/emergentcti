export type SSOProviderType = 'azure_ad' | 'google' | 'oidc';

export interface SSOProviderPublic {
  provider_type: string;
  display_name: string;
}

export interface SSOProviderResponse {
  id: string;
  provider_type: string;
  display_name: string;
  enabled: boolean;
  provider_config: Record<string, string>;
  default_role: 'admin' | 'analyst' | 'readonly';
  allowed_domains: string[] | null;
  auto_create_users: boolean;
  created_at: string;
  updated_at: string;
}

export interface SSOProviderConfigUpdate {
  display_name?: string;
  enabled?: boolean;
  client_id?: string;
  client_secret?: string;
  tenant_id?: string;
  issuer_url?: string;
  allowed_domains?: string[];
  default_role?: 'admin' | 'analyst' | 'readonly';
  auto_create_users?: boolean;
}

export interface SSOAuthorizeResponse {
  authorization_url: string;
}

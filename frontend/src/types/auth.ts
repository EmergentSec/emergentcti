export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  role?: 'admin' | 'analyst' | 'readonly';
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'analyst' | 'readonly';
  auth_provider: 'local' | 'azure_ad' | 'google' | 'oidc';
  is_active: boolean;
  has_api_key: boolean;
  created_at: string;
}

export interface ApiKeyResponse {
  api_key: string;
}

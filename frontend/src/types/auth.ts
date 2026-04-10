export interface AuthUser {
  id: string
  username: string
  role: 'admin' | 'user'
}

export interface LoginRequest {
  username: string
  password: string
}

// Keep ApiKey types as they're used in settings
export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  is_active: boolean
  created_at: string
  last_used_at: string | null
  description: string | null
}

export interface ApiKeyCreate {
  name: string
  description?: string
}

export interface ApiKeyCreateResponse extends ApiKey {
  key: string
}

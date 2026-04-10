import api from './client'
import type { AuthUser, LoginRequest } from '@/types/auth'

export async function login(credentials: LoginRequest): Promise<AuthUser> {
  const response = await api.post<AuthUser>('/auth/login', credentials)
  return response.data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function getMe(): Promise<AuthUser> {
  const response = await api.get<{ type: string; id: string; name: string; role: string }>('/auth/me')
  // Normalize the /me response (which has 'name' not 'username') to AuthUser
  return {
    id: response.data.id,
    username: response.data.name,
    role: response.data.role as 'admin' | 'user',
  }
}


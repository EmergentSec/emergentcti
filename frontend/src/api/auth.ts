import client from './client';
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
  ApiKeyResponse,
} from '@/types/auth';

export async function getUsers(): Promise<UserResponse[]> {
  const { data } = await client.get<UserResponse[]>('/auth/users');
  return data;
}

export async function registerUser(data: RegisterRequest): Promise<UserResponse> {
  const { data: user } = await client.post<UserResponse>('/auth/register', data);
  return user;
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const response = await client.post<TokenResponse>('/auth/login', data);
  return response.data;
}

export async function register(data: RegisterRequest): Promise<UserResponse> {
  const response = await client.post<UserResponse>('/auth/register', data);
  return response.data;
}

export async function refreshToken(
  refresh_token: string
): Promise<TokenResponse> {
  const response = await client.post<TokenResponse>('/auth/refresh', {
    refresh_token,
  });
  return response.data;
}

export async function getMe(): Promise<UserResponse> {
  const response = await client.get<UserResponse>('/auth/me');
  return response.data;
}

export async function generateApiKey(): Promise<ApiKeyResponse> {
  const response = await client.post<ApiKeyResponse>('/auth/api-key');
  return response.data;
}

export async function updateUser(
  userId: string,
  data: { role?: string; is_active?: boolean }
): Promise<UserResponse> {
  const response = await client.put<UserResponse>(`/auth/users/${userId}`, data);
  return response.data;
}

export async function deleteUser(userId: string): Promise<void> {
  await client.delete(`/auth/users/${userId}`);
}

export async function bulkUpdateUsers(
  ids: string[],
  updates: { role?: string; is_active?: boolean }
): Promise<{ updated: number }> {
  const response = await client.patch<{ updated: number }>('/auth/users/bulk', {
    ids,
    ...updates,
  });
  return response.data;
}

export async function bulkDeleteUsers(ids: string[]): Promise<{ deleted: number }> {
  const response = await client.delete<{ deleted: number }>('/auth/users/bulk', {
    data: { ids },
  });
  return response.data;
}

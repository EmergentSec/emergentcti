import api from './client'
import type { User, UserCreate, UserUpdate, PasswordChange } from '@/types/user'

export async function listUsers(): Promise<User[]> {
  const response = await api.get<User[]>('/settings/users')
  return response.data
}

export async function createUser(data: UserCreate): Promise<User> {
  const response = await api.post<User>('/settings/users', data)
  return response.data
}

export async function updateUser(id: string, data: UserUpdate): Promise<User> {
  const response = await api.put<User>(`/settings/users/${id}`, data)
  return response.data
}

export async function deleteUser(id: string): Promise<void> {
  await api.delete(`/settings/users/${id}`)
}

export async function changePassword(id: string, data: PasswordChange): Promise<void> {
  await api.put(`/settings/users/${id}/password`, data)
}

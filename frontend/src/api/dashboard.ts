import api from './client'
import type { DashboardStats } from '@/types/dashboard'

export async function getStats(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>('/stats')
  return data
}

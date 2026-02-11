import { useQuery } from '@tanstack/react-query';
import client from '@/api/client';

export interface TrendDataPoint {
  date: string;
  count: number;
}

export interface TLPDataPoint {
  tlp: string;
  count: number;
}

export interface TagDataPoint {
  tag: string;
  count: number;
}

async function getObservableTrend(days: number): Promise<TrendDataPoint[]> {
  const response = await client.get<TrendDataPoint[]>('/dashboard/trend', {
    params: { days },
  });
  return response.data;
}

async function getTLPDistribution(): Promise<TLPDataPoint[]> {
  const response = await client.get<TLPDataPoint[]>(
    '/dashboard/tlp-distribution'
  );
  return response.data;
}

async function getTopTags(limit: number): Promise<TagDataPoint[]> {
  const response = await client.get<TagDataPoint[]>('/dashboard/top-tags', {
    params: { limit },
  });
  return response.data;
}

export function useObservableTrend(days: number = 30) {
  return useQuery({
    queryKey: ['dashboard', 'trend', days],
    queryFn: () => getObservableTrend(days),
    staleTime: 30_000,
  });
}

export function useTLPDistribution() {
  return useQuery({
    queryKey: ['dashboard', 'tlp-distribution'],
    queryFn: getTLPDistribution,
    staleTime: 30_000,
  });
}

export function useTopTags(limit: number = 15) {
  return useQuery({
    queryKey: ['dashboard', 'top-tags', limit],
    queryFn: () => getTopTags(limit),
    staleTime: 30_000,
  });
}

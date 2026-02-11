import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getFeeds,
  getFeed,
  createFeed,
  updateFeed,
  deleteFeed,
  triggerFeed,
  getFeedRuns,
  bulkUpdateFeeds,
  bulkDeleteFeeds,
  bulkTriggerFeeds,
} from '@/api/feeds';
import type { FeedCreateRequest, FeedUpdateRequest } from '@/types/feed';

export function useFeeds() {
  return useQuery({
    queryKey: ['feeds'],
    queryFn: getFeeds,
    staleTime: 30_000,
  });
}

export function useFeed(id: string) {
  return useQuery({
    queryKey: ['feeds', id],
    queryFn: () => getFeed(id),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useFeedRuns(id: string) {
  return useQuery({
    queryKey: ['feeds', id, 'runs'],
    queryFn: () => getFeedRuns(id),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useCreateFeed() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: FeedCreateRequest) => createFeed(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });
}

export function useUpdateFeed() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: FeedUpdateRequest }) =>
      updateFeed(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });
}

export function useDeleteFeed() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteFeed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });
}

export function useTriggerFeed() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => triggerFeed(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['feeds', id, 'runs'] });
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });
}

export function useBulkUpdateFeeds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ids, updates }: { ids: string[]; updates: { enabled?: boolean } }) =>
      bulkUpdateFeeds(ids, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });
}

export function useBulkDeleteFeeds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => bulkDeleteFeeds(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });
}

export function useBulkTriggerFeeds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => bulkTriggerFeeds(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });
}

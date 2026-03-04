import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getFeeds, getFeed, createFeed, updateFeed, deleteFeed, triggerFeed, getFeedRuns } from '@/api/feeds'
import type { FeedCreate, FeedUpdate } from '@/types/feed'

export function useFeeds() {
  return useQuery({
    queryKey: ['feeds'],
    queryFn: getFeeds,
  })
}

export function useFeed(id: string | null) {
  return useQuery({
    queryKey: ['feed', id],
    queryFn: () => getFeed(id!),
    enabled: !!id,
  })
}

export function useFeedRuns(id: string | null) {
  return useQuery({
    queryKey: ['feedRuns', id],
    queryFn: () => getFeedRuns(id!),
    enabled: !!id,
  })
}

export function useCreateFeed() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: FeedCreate) => createFeed(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
    },
  })
}

export function useUpdateFeed() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: FeedUpdate }) => updateFeed(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
    },
  })
}

export function useDeleteFeed() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteFeed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
    },
  })
}

export function useTriggerFeed() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => triggerFeed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['feedRuns'] })
    },
  })
}

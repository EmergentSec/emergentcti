import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listCorrelationRules,
  createCorrelationRule,
  updateCorrelationRule,
  deleteCorrelationRule,
  listCorrelationEvents,
  triggerCorrelationRun,
} from '@/api/correlations';
import type {
  CorrelationRuleCreate,
  CorrelationRuleUpdate,
} from '@/types/correlation';

// --- Correlation Rules ---

export function useCorrelationRules() {
  return useQuery({
    queryKey: ['correlation-rules'],
    queryFn: listCorrelationRules,
    staleTime: 30_000,
  });
}

export function useCreateCorrelationRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CorrelationRuleCreate) => createCorrelationRule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['correlation-rules'] });
    },
  });
}

export function useUpdateCorrelationRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: CorrelationRuleUpdate }) =>
      updateCorrelationRule(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['correlation-rules'] });
    },
  });
}

export function useDeleteCorrelationRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteCorrelationRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['correlation-rules'] });
    },
  });
}

// --- Correlation Events ---

export function useCorrelationEvents(page: number = 1, size: number = 20) {
  return useQuery({
    queryKey: ['correlation-events', page, size],
    queryFn: () => listCorrelationEvents({ page, size }),
    staleTime: 30_000,
  });
}

// --- Trigger ---

export function useTriggerCorrelationRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => triggerCorrelationRun(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['correlation-events'] });
    },
  });
}

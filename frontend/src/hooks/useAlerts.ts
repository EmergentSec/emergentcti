import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listAlertRules,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
  listAlertEvents,
  listWebhooks,
  createWebhook,
  updateWebhook,
  deleteWebhook,
  testWebhook,
} from '@/api/alerts';
import type {
  AlertRuleCreate,
  AlertRuleUpdate,
  WebhookConfigCreate,
  WebhookConfigUpdate,
} from '@/types/alert';

// --- Alert Rules ---

export function useAlertRules() {
  return useQuery({
    queryKey: ['alertRules'],
    queryFn: listAlertRules,
    staleTime: 30_000,
  });
}

export function useCreateAlertRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AlertRuleCreate) => createAlertRule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alertRules'] });
    },
  });
}

export function useUpdateAlertRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AlertRuleUpdate }) =>
      updateAlertRule(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alertRules'] });
    },
  });
}

export function useDeleteAlertRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAlertRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alertRules'] });
    },
  });
}

// --- Alert Events ---

export function useAlertEvents(params: {
  page?: number;
  size?: number;
  rule_id?: string;
}) {
  return useQuery({
    queryKey: ['alertEvents', params],
    queryFn: () => listAlertEvents(params),
    staleTime: 30_000,
  });
}

// --- Webhooks ---

export function useWebhooks() {
  return useQuery({
    queryKey: ['webhooks'],
    queryFn: listWebhooks,
    staleTime: 30_000,
  });
}

export function useCreateWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WebhookConfigCreate) => createWebhook(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useUpdateWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WebhookConfigUpdate }) =>
      updateWebhook(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useDeleteWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteWebhook(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useTestWebhook() {
  return useMutation({
    mutationFn: (id: string) => testWebhook(id),
  });
}

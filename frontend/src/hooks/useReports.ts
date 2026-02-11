import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listReports,
  createReport,
  deleteReport,
} from '@/api/reports';
import type { ReportCreate } from '@/types/report';

export function useReports(params: { page?: number; size?: number } = {}) {
  return useQuery({
    queryKey: ['reports', params],
    queryFn: () => listReports(params),
    staleTime: 10_000,
  });
}

export function useCreateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ReportCreate) => createReport(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
  });
}

export function useDeleteReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteReport(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
  });
}

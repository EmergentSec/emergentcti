import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getReports,
  getReportSources,
  getReport,
  createReport,
  updateReport,
  deleteReport,
  uploadReportAttachment,
  removeReportAttachment,
  linkReportObservable,
  unlinkReportObservable,
  getObservableReports,
  extractReportIndicators,
  importReportIndicators,
} from '@/api/reports'
import type { ImportRequest } from '@/types/reportIocExtraction'
import type { ReportCreate, ReportFilters, ReportUpdate } from '@/types/report'

export function useReports(filters: ReportFilters) {
  return useQuery({
    queryKey: ['reports', filters],
    queryFn: () => getReports(filters),
  })
}

export function useReportSources() {
  return useQuery({
    queryKey: ['reportSources'],
    queryFn: getReportSources,
  })
}

export function useReport(id: string | null) {
  return useQuery({
    queryKey: ['report', id],
    queryFn: () => getReport(id!),
    enabled: !!id,
  })
}

export function useObservableReports(observableId: string | null) {
  return useQuery({
    queryKey: ['observableReports', observableId],
    queryFn: () => getObservableReports(observableId!),
    enabled: !!observableId,
  })
}

export function useCreateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ReportCreate) => createReport(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useUpdateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ReportUpdate }) => updateReport(id, data),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['report', id] })
    },
  })
}

export function useDeleteReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteReport(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useUploadReportAttachment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => uploadReportAttachment(id, file),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['report', id] })
    },
  })
}

export function useRemoveReportAttachment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => removeReportAttachment(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['report', id] })
    },
  })
}

export function useLinkReportObservable() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reportId, observableId }: { reportId: string; observableId: string }) =>
      linkReportObservable(reportId, observableId),
    onSuccess: (_data, { reportId, observableId }) => {
      queryClient.invalidateQueries({ queryKey: ['report', reportId] })
      queryClient.invalidateQueries({ queryKey: ['observableReports', observableId] })
    },
  })
}

export function useUnlinkReportObservable() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reportId, observableId }: { reportId: string; observableId: string }) =>
      unlinkReportObservable(reportId, observableId),
    onSuccess: (_data, { reportId, observableId }) => {
      queryClient.invalidateQueries({ queryKey: ['report', reportId] })
      queryClient.invalidateQueries({ queryKey: ['observableReports', observableId] })
    },
  })
}

export function useExtractReportIndicators() {
  return useMutation({
    mutationFn: (reportId: string) => extractReportIndicators(reportId),
  })
}

export function useImportReportIndicators() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reportId, payload }: { reportId: string; payload: ImportRequest }) =>
      importReportIndicators(reportId, payload),
    onSuccess: (_data, { reportId }) => {
      queryClient.invalidateQueries({ queryKey: ['report', reportId] })
    },
  })
}

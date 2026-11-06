import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/contexts/ToastContext'
import {
  importFailureMessage,
  importFailureShownInline,
  importSuccessMessage,
} from '@/lib/importRequest'
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
  setReportTags,
  ReportTagsSaveError,
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
    onError: (err) => {
      if (err instanceof ReportTagsSaveError) {
        queryClient.invalidateQueries({ queryKey: ['reports'] })
        queryClient.invalidateQueries({ queryKey: ['report', err.report.id] })
      }
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
  const { toast } = useToast()
  return useMutation({
    mutationFn: ({ reportId, payload }: { reportId: string; payload: ImportRequest }) =>
      importReportIndicators(reportId, payload),
    onSuccess: (result, { reportId }) => {
      queryClient.invalidateQueries({ queryKey: ['report', reportId] })
      queryClient.invalidateQueries({ queryKey: ['observables'] })
      queryClient.invalidateQueries({ queryKey: ['observableReports'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      // Hook callbacks run even if the review dialog has unmounted.
      toast(importSuccessMessage(result), 'success')
    },
    onError: (err) => {
      // While the dialog is open it shows the failure inline (including row
      // highlights). After dismiss, this is the only place the analyst hears
      // the outcome — including a timeout whose commit state is unknown.
      if (importFailureShownInline()) return
      toast(importFailureMessage(err), 'error')
    },
  })
}

export function useSetReportTags() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reportId, tags }: { reportId: string; tags: string[] }) =>
      setReportTags(reportId, tags),
    onSuccess: (_data, { reportId }) => {
      queryClient.invalidateQueries({ queryKey: ['report', reportId] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

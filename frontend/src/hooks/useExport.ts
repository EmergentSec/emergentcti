import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  exportSTIX,
  exportCSV,
  exportJSON,
  previewCSVImport,
  importCSV,
  importSTIX,
} from '@/api/export';
import type { ExportParams } from '@/types/export';

export function useExportSTIX() {
  return useMutation({
    mutationFn: (params: ExportParams) => exportSTIX(params),
  });
}

export function useExportCSV() {
  return useMutation({
    mutationFn: (params: ExportParams) => exportCSV(params),
  });
}

export function useExportJSON() {
  return useMutation({
    mutationFn: (params: ExportParams) => exportJSON(params),
  });
}

export function useCSVPreview() {
  return useMutation({
    mutationFn: ({
      file,
      columnMapping,
    }: {
      file: File;
      columnMapping?: Record<string, string>;
    }) => previewCSVImport(file, columnMapping),
  });
}

export function useImportCSV() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      columnMapping,
    }: {
      file: File;
      columnMapping: Record<string, string>;
    }) => importCSV(file, columnMapping),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}

export function useImportSTIX() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => importSTIX(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}

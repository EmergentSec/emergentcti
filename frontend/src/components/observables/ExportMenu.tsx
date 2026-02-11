import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { useExportSTIX, useExportCSV, useExportJSON } from '@/hooks/useExport';
import { useToast } from '@/contexts/ToastContext';
import type { ExportParams } from '@/types/export';

interface ExportMenuProps {
  filters: ExportParams;
}

export function ExportMenu({ filters }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const exportSTIX = useExportSTIX();
  const exportCSV = useExportCSV();
  const exportJSON = useExportJSON();
  const { addToast } = useToast();

  const isExporting =
    exportSTIX.isPending || exportCSV.isPending || exportJSON.isPending;

  const handleExport = (
    format: 'stix' | 'csv' | 'json',
    mutation: typeof exportSTIX
  ) => {
    setOpen(false);
    mutation.mutate(filters, {
      onSuccess: () => {
        addToast(`Exported as ${format.toUpperCase()} successfully`, 'success');
      },
      onError: () => {
        addToast(`Failed to export as ${format.toUpperCase()}`, 'error');
      },
    });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger onClick={() => setOpen(!open)}>
        <Button variant="outline" disabled={isExporting}>
          {isExporting ? 'Exporting...' : 'Export'}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent open={open} onClose={() => setOpen(false)} align="end">
        <DropdownMenuLabel>Export Format</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => handleExport('stix', exportSTIX)}>
          Export as STIX 2.1
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleExport('csv', exportCSV)}>
          Export as CSV
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleExport('json', exportJSON)}>
          Export as JSON
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

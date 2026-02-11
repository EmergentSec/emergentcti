import { useState, type FormEvent } from 'react';
import { formatRelativeTime } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { useReports, useCreateReport, useDeleteReport } from '@/hooks/useReports';
import { getReportDownloadUrl } from '@/api/reports';
import { useToast } from '@/contexts/ToastContext';
import type { ReportCreate, ReportResponse } from '@/types/report';

const REPORT_TYPES = [
  { value: 'threat_summary', label: 'Threat Summary' },
  { value: 'observable_report', label: 'Observable Report' },
  { value: 'campaign_brief', label: 'Campaign Brief' },
] as const;

function statusBadge(status: string) {
  switch (status) {
    case 'pending':
      return (
        <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
          Pending
        </Badge>
      );
    case 'generating':
      return (
        <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
          Generating
        </Badge>
      );
    case 'ready':
      return (
        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
          Ready
        </Badge>
      );
    case 'failed':
      return (
        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
          Failed
        </Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function reportTypeLabel(type: string): string {
  const found = REPORT_TYPES.find((t) => t.value === type);
  return found ? found.label : type;
}

function GenerateReportForm({ onClose }: { onClose: () => void }) {
  const createMutation = useCreateReport();
  const { addToast } = useToast();

  const [title, setTitle] = useState('');
  const [reportType, setReportType] = useState<ReportCreate['report_type']>('threat_summary');
  const [format] = useState<'html'>('html');

  // Parameters for each type
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [observableId, setObservableId] = useState('');
  const [campaignId, setCampaignId] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    let parameters: Record<string, unknown> = {};
    if (reportType === 'threat_summary') {
      if (dateFrom) parameters.date_from = dateFrom;
      if (dateTo) parameters.date_to = dateTo;
    } else if (reportType === 'observable_report') {
      if (!observableId.trim()) {
        addToast('Observable ID is required', 'error');
        return;
      }
      parameters.observable_id = observableId.trim();
    } else if (reportType === 'campaign_brief') {
      if (!campaignId.trim()) {
        addToast('Campaign ID is required', 'error');
        return;
      }
      parameters.campaign_id = campaignId.trim();
    }

    const data: ReportCreate = {
      title: title || `${reportTypeLabel(reportType)} - ${new Date().toLocaleDateString()}`,
      report_type: reportType,
      parameters,
      format,
    };

    createMutation.mutate(data, {
      onSuccess: () => {
        addToast('Report generation queued', 'success');
        onClose();
      },
      onError: () => addToast('Failed to create report', 'error'),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="report-title" className="text-sm font-medium">
          Title
        </label>
        <Input
          id="report-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Auto-generated if empty"
        />
      </div>

      <div className="space-y-2">
        <label htmlFor="report-type" className="text-sm font-medium">
          Report Type
        </label>
        <Select
          id="report-type"
          value={reportType}
          onChange={(e) =>
            setReportType(e.target.value as ReportCreate['report_type'])
          }
        >
          {REPORT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
      </div>

      {/* Dynamic parameters */}
      {reportType === 'threat_summary' && (
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <label htmlFor="date-from" className="text-sm font-medium">
              Date From
            </label>
            <Input
              id="date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="date-to" className="text-sm font-medium">
              Date To
            </label>
            <Input
              id="date-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
        </div>
      )}

      {reportType === 'observable_report' && (
        <div className="space-y-2">
          <label htmlFor="observable-id" className="text-sm font-medium">
            Observable ID
          </label>
          <Input
            id="observable-id"
            value={observableId}
            onChange={(e) => setObservableId(e.target.value)}
            placeholder="Enter observable UUID"
            required
          />
        </div>
      )}

      {reportType === 'campaign_brief' && (
        <div className="space-y-2">
          <label htmlFor="campaign-id" className="text-sm font-medium">
            Campaign ID
          </label>
          <Input
            id="campaign-id"
            value={campaignId}
            onChange={(e) => setCampaignId(e.target.value)}
            placeholder="Enter campaign UUID"
            required
          />
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium">Format</label>
        <div className="text-sm text-muted-foreground">HTML</div>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? 'Generating...' : 'Generate Report'}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function ReportsPage() {
  const [page] = useState(1);
  const { data: reportsData, isLoading } = useReports({ page, size: 20 });
  const deleteMutation = useDeleteReport();
  const { addToast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleDelete = (report: ReportResponse) => {
    if (window.confirm(`Delete report "${report.title}"?`)) {
      deleteMutation.mutate(report.id, {
        onSuccess: () => addToast('Report deleted', 'success'),
        onError: () => addToast('Failed to delete report', 'error'),
      });
    }
  };

  const handleDownload = (report: ReportResponse) => {
    const url = getReportDownloadUrl(report.id);
    const link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
          <p className="text-muted-foreground">
            Generate and download threat intelligence reports
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>+ Generate Report</Button>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground py-8 text-center">
          Loading reports...
        </div>
      ) : !reportsData?.items.length ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            <p>No reports generated yet.</p>
            <p className="text-sm mt-1">
              Click "Generate Report" to create a threat intelligence report.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Format</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reportsData.items.map((report) => (
                <TableRow key={report.id}>
                  <TableCell className="font-medium text-sm">
                    {report.title}
                    {report.error_message && (
                      <span
                        className="block text-xs text-red-400 mt-0.5 truncate max-w-xs"
                        title={report.error_message}
                      >
                        {report.error_message}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {reportTypeLabel(report.report_type)}
                    </Badge>
                  </TableCell>
                  <TableCell>{statusBadge(report.status)}</TableCell>
                  <TableCell className="text-sm uppercase">
                    {report.format}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatRelativeTime(report.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      {report.status === 'ready' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload(report)}
                        >
                          Download
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleDelete(report)}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogClose onClose={() => setDialogOpen(false)} />
          <DialogHeader>
            <DialogTitle>Generate Report</DialogTitle>
          </DialogHeader>
          <GenerateReportForm onClose={() => setDialogOpen(false)} />
        </DialogContent>
      </Dialog>
    </div>
  );
}

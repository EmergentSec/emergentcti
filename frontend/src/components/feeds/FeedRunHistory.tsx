import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { cn, formatDate } from '@/lib/utils';
import type { FeedRunResponse } from '@/types/feed';

interface FeedRunHistoryProps {
  runs: FeedRunResponse[];
  isLoading?: boolean;
}

function getStatusBadge(status: string) {
  const styles: Record<string, string> = {
    completed: 'bg-green-500/20 text-green-400 border-green-500/30',
    running: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
    pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  };

  return (
    <Badge
      variant="outline"
      className={cn('capitalize', styles[status] || '')}
    >
      {status}
    </Badge>
  );
}

export function FeedRunHistory({ runs, isLoading }: FeedRunHistoryProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse rounded bg-muted"
          />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        <p>No run history available</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Status</TableHead>
          <TableHead>Started</TableHead>
          <TableHead>Completed</TableHead>
          <TableHead>Ingested</TableHead>
          <TableHead>Error Message</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            <TableCell>{getStatusBadge(run.status)}</TableCell>
            <TableCell className="text-sm whitespace-nowrap">
              {formatDate(run.started_at)}
            </TableCell>
            <TableCell className="text-sm whitespace-nowrap">
              {run.completed_at ? formatDate(run.completed_at) : '-'}
            </TableCell>
            <TableCell className="text-sm tabular-nums">
              {run.observables_ingested.toLocaleString()}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
              {run.error_message || '-'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

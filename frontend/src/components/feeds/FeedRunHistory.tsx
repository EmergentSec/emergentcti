import { useFeedRuns } from '@/hooks/useFeeds'
import { Badge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { formatDate } from '@/lib/utils'
import type { FeedRun } from '@/types/feed'

interface FeedRunHistoryProps {
  feedId: string
}

function formatDuration(started: string, completed: string | null): string {
  if (!completed) return 'In progress'
  const ms = new Date(completed).getTime() - new Date(started).getTime()
  if (ms < 1000) return `${ms}ms`
  const secs = Math.floor(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const remainSecs = secs % 60
  return `${mins}m ${remainSecs}s`
}

function statusBadge(status: FeedRun['status']) {
  switch (status) {
    case 'success':
      return <Badge variant="success">Success</Badge>
    case 'failure':
      return <Badge variant="destructive">Failed</Badge>
    case 'running':
      return (
        <Badge variant="secondary">
          <span className="mr-1 inline-block h-2 w-2 animate-pulse-dot rounded-full bg-blue-400" />
          Running
        </Badge>
      )
  }
}

export function FeedRunHistory({ feedId }: FeedRunHistoryProps) {
  const { data: runs, isLoading, error } = useFeedRuns(feedId)

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  if (error) {
    return (
      <p className="text-sm text-destructive-foreground">Failed to load run history</p>
    )
  }

  if (!runs || runs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No runs recorded yet</p>
    )
  }

  // Show last 20 runs
  const recentRuns = runs.slice(0, 20)

  return (
    <div>
      <h4 className="mb-2 text-sm font-medium text-foreground">
        Run History ({runs.length} total)
      </h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Status</TableHead>
            <TableHead>Started</TableHead>
            <TableHead>Duration</TableHead>
            <TableHead className="text-right">Ingested</TableHead>
            <TableHead className="text-right">New</TableHead>
            <TableHead>Error</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {recentRuns.map((run) => (
            <TableRow key={run.id}>
              <TableCell>{statusBadge(run.status)}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {formatDate(run.started_at)}
              </TableCell>
              <TableCell className="text-sm tabular-nums">
                {formatDuration(run.started_at, run.completed_at)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {run.observables_ingested}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {run.observables_new}
              </TableCell>
              <TableCell className="max-w-[200px] truncate text-sm text-destructive">
                {run.error_message || ''}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

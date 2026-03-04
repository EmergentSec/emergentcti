import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { formatRelativeTime } from '@/lib/utils'
import type { FeedHealth } from '@/types/dashboard'

interface RecentFeedRunsProps {
  feeds: FeedHealth[]
}

function statusBadge(status: string | null) {
  if (!status) return <Badge variant="outline">Never Run</Badge>
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
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

export function RecentFeedRuns({ feeds }: RecentFeedRunsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Feed Status</CardTitle>
      </CardHeader>
      <CardContent>
        {feeds.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground py-4">
            No active feeds
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Feed Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Observables</TableHead>
                <TableHead className="text-right">Last Run</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {feeds.map((feed) => (
                <TableRow key={feed.id}>
                  <TableCell className="font-medium">{feed.name}</TableCell>
                  <TableCell>{statusBadge(feed.last_run_status)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {feed.observable_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatRelativeTime(feed.last_run_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/Table';
import { compactNumber } from '@/lib/dashboardFormat';
import { formatRelativeTime } from '@/lib/utils';
import type { FeedHealth } from '@/types/dashboard';

interface FeedStatusTableProps {
  feeds: FeedHealth[];
}

function StatusDot({ status }: { status: FeedHealth['last_run_status'] }) {
  if (status === 'running') {
    return (
      <span
        className="inline-block h-2 w-2 animate-pulse-dot rounded-full bg-cat-blue"
        title="Running"
      />
    );
  }
  if (status === 'failure') {
    return (
      <span
        className="inline-block h-2 w-2 rounded-full bg-conf-critical"
        title="Failed"
      />
    );
  }
  // success or null → green
  return (
    <span
      className="inline-block h-2 w-2 rounded-full bg-cat-green"
      title="Success"
    />
  );
}

export function FeedStatusTable({ feeds }: FeedStatusTableProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-[15px]">Feed status</CardTitle>
          <Link
            to="/feeds"
            className="text-[13px] text-muted-foreground hover:text-foreground transition-colors"
          >
            View all
          </Link>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table className="table-fixed text-sm">
          <colgroup>
            <col className="w-8" />
            <col />
            <col className="w-20" />
            <col className="w-20" />
          </colgroup>
          <TableBody>
            {feeds.map((feed) => (
              <TableRow
                key={feed.id}
                className="hover:bg-hover"
              >
                <TableCell className="w-8 pl-5 pr-0">
                  <StatusDot status={feed.last_run_status} />
                </TableCell>
                <TableCell
                  className="truncate font-medium text-foreground"
                  title={feed.name}
                >
                  {feed.name}
                </TableCell>
                <TableCell className="whitespace-nowrap text-right font-mono text-xs text-muted-foreground">
                  {compactNumber(feed.observable_count)}
                </TableCell>
                <TableCell className="whitespace-nowrap pr-5 text-right text-xs text-muted-foreground">
                  {formatRelativeTime(feed.last_run_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

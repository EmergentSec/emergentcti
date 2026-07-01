import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
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
        <table className="w-full text-[13px]">
          <tbody>
            {feeds.map((feed) => (
              <tr
                key={feed.id}
                className="flex items-center gap-3 border-t border-border px-5 py-2.5 hover:bg-hover"
              >
                <td className="flex-none">
                  <StatusDot status={feed.last_run_status} />
                </td>
                <td className="min-w-0 flex-1 truncate font-medium text-foreground">
                  {feed.name}
                </td>
                <td className="flex-none font-mono text-[12px] text-muted-foreground">
                  {compactNumber(feed.observable_count)}
                </td>
                <td className="flex-none text-[12px] text-muted-foreground">
                  {formatRelativeTime(feed.last_run_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

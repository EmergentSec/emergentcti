import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { FeedRunSummary } from '@/types/api';

interface FeedHealthPanelProps {
  runs: FeedRunSummary[] | undefined;
  isLoading?: boolean;
}

function getStatusStyles(status: string): string {
  switch (status) {
    case 'success':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'running':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'failure':
      return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'pending':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

function getStatusDot(status: string): string {
  switch (status) {
    case 'success':
      return 'bg-green-500';
    case 'running':
      return 'bg-blue-500 animate-pulse';
    case 'failure':
      return 'bg-red-500';
    case 'pending':
      return 'bg-yellow-500';
    default:
      return 'bg-gray-500';
  }
}

export function FeedHealthPanel({ runs, isLoading }: FeedHealthPanelProps) {
  if (isLoading || !runs) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Feed Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-h-[300px] overflow-y-auto space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded bg-muted"
              />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (runs.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Feed Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[200px] items-center justify-center text-muted-foreground">
            No recent feed activity
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent Feed Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-h-[300px] overflow-y-auto space-y-3">
          {runs.map((run, idx) => (
            <div
              key={`${run.feed_id}-${idx}`}
              className="flex items-center justify-between rounded-lg border p-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className={cn(
                    'h-2.5 w-2.5 shrink-0 rounded-full',
                    getStatusDot(run.status)
                  )}
                />
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">
                    {run.feed_name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatRelativeTime(run.started_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <div className="text-right text-xs">
                  <span className="text-green-400 tabular-nums">
                    +{run.observables_created}
                  </span>
                  {run.errors > 0 && (
                    <span className="text-red-400 ml-2 tabular-nums">
                      {run.errors} err
                    </span>
                  )}
                </div>
                <Badge
                  variant="outline"
                  className={cn('text-xs capitalize', getStatusStyles(run.status))}
                >
                  {run.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

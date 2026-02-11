import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from '@/components/ui/dialog';
import { formatRelativeTime } from '@/lib/utils';
import type { DashboardStats } from '@/types/api';

interface StatsGridProps {
  stats: DashboardStats | undefined;
  isLoading?: boolean;
}

interface StatCardData {
  label: string;
  value: number | string;
  icon: string;
  description: string;
}

export function StatsGrid({ stats, isLoading }: StatsGridProps) {
  const [showErrorDialog, setShowErrorDialog] = useState(false);
  const navigate = useNavigate();

  if (isLoading || !stats) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="h-16 animate-pulse rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards: StatCardData[] = [
    {
      label: 'Total Observables',
      value: stats.total_observables.toLocaleString(),
      icon: '\u25C9',
      description: 'Tracked indicators',
    },
    {
      label: 'Today',
      value: stats.observables_today.toLocaleString(),
      icon: '\u2191',
      description: 'New today',
    },
    {
      label: 'Active Feeds',
      value: `${stats.active_feeds}/${stats.total_feeds}`,
      icon: '\u21BB',
      description: 'Feed sources',
    },
  ];

  const hasErrors = stats.feeds_with_errors > 0;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Card key={card.label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.label}
              </CardTitle>
              <span className="text-2xl text-muted-foreground">{card.icon}</span>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {card.description}
              </p>
            </CardContent>
          </Card>
        ))}

        {/* Feed Errors card - clickable when errors exist */}
        <Card
          className={
            hasErrors
              ? 'cursor-pointer hover:border-amber-500/50 transition-colors'
              : undefined
          }
          onClick={() => {
            if (hasErrors) {
              setShowErrorDialog(true);
            }
          }}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Feed Errors
            </CardTitle>
            <span className="text-2xl text-muted-foreground">{'\u26A0'}</span>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.feeds_with_errors}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Feeds with errors
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Feed Errors Dialog */}
      <Dialog open={showErrorDialog} onOpenChange={setShowErrorDialog}>
        <DialogContent>
          <DialogClose onClose={() => setShowErrorDialog(false)} />
          <DialogHeader>
            <DialogTitle>Feeds with Errors</DialogTitle>
          </DialogHeader>
          {stats.errored_feeds.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No feed errors</p>
          ) : (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {stats.errored_feeds.map((feed) => (
                <div
                  key={feed.feed_id}
                  className="flex flex-col gap-1 rounded-md border p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => {
                    setShowErrorDialog(false);
                    navigate('/feeds');
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold">{feed.feed_name}</span>
                    {feed.last_run_at && (
                      <span className="text-xs text-muted-foreground">
                        {formatRelativeTime(feed.last_run_at)}
                      </span>
                    )}
                  </div>
                  {feed.error_message && (
                    <p className="text-xs text-red-400 line-clamp-2">
                      {feed.error_message}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, formatRelativeTime, FEED_TYPE_LABELS } from '@/lib/utils';
import { canManageFeeds, canTriggerFeed } from '@/lib/permissions';
import { useAuth } from '@/hooks/useAuth';
import type { FeedResponse } from '@/types/feed';

interface FeedCardProps {
  feed: FeedResponse;
  onTrigger: (id: string) => void;
  onEdit: (feed: FeedResponse) => void;
  onDelete: (id: string) => void;
  isTriggering?: boolean;
}

export function FeedCard({
  feed,
  onTrigger,
  onEdit,
  onDelete,
  isTriggering,
}: FeedCardProps) {
  const { user } = useAuth();

  return (
    <Card className="transition-colors hover:border-primary/30">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'h-2.5 w-2.5 rounded-full',
                feed.enabled ? 'bg-green-500' : 'bg-gray-500'
              )}
              title={feed.enabled ? 'Enabled' : 'Disabled'}
            />
            <CardTitle className="text-base">{feed.name}</CardTitle>
          </div>
          <Badge variant="outline" className="text-xs">
            {FEED_TYPE_LABELS[feed.feed_type] || feed.feed_type}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {feed.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {feed.description}
          </p>
        )}

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-muted-foreground">Schedule</p>
            <p className="font-medium font-mono text-xs">
              {feed.schedule_cron || 'Manual'}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Last Run</p>
            <p className="font-medium">
              {feed.last_run_at
                ? formatRelativeTime(feed.last_run_at)
                : 'Never'}
            </p>
          </div>
          {feed.default_ttl_days && (
            <div>
              <p className="text-muted-foreground">TTL</p>
              <p className="font-medium">
                {feed.default_ttl_days} day{feed.default_ttl_days !== 1 ? 's' : ''}
              </p>
            </div>
          )}
        </div>

        {feed.url && (
          <div className="text-xs text-muted-foreground font-mono truncate" title={feed.url}>
            {feed.url}
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          {canTriggerFeed(user) && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onTrigger(feed.id)}
              disabled={isTriggering || !feed.enabled}
            >
              {isTriggering ? 'Running...' : 'Run Now'}
            </Button>
          )}
          {canManageFeeds(user) && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onEdit(feed)}
            >
              Edit
            </Button>
          )}
          {canManageFeeds(user) && (
            <Button
              size="sm"
              variant="ghost"
              className="text-red-400 hover:text-red-300"
              onClick={() => onDelete(feed.id)}
            >
              Delete
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

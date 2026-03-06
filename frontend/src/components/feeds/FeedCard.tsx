import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { FeedRunHistory } from './FeedRunHistory'
import { useUpdateFeed, useTriggerFeed, useDeleteFeed } from '@/hooks/useFeeds'
import { useToast } from '@/contexts/ToastContext'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { Feed } from '@/types/feed'

interface FeedCardProps {
  feed: Feed
}

const feedTypeBadge: Record<string, string> = {
  api: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  file: 'bg-green-500/20 text-green-400 border-green-500/30',
  scraper: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
}

function runStatusIndicator(status: string | null) {
  if (!status) return null
  switch (status) {
    case 'success':
      return <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" title="Last run succeeded" />
    case 'failure':
      return <span className="inline-block h-2 w-2 rounded-full bg-red-500" title="Last run failed" />
    case 'running':
      return <span className="inline-block h-2 w-2 animate-pulse-dot rounded-full bg-blue-500" title="Running" />
    default:
      return null
  }
}

export function FeedCard({ feed }: FeedCardProps) {
  const [expanded, setExpanded] = useState(false)
  const updateFeed = useUpdateFeed()
  const triggerFeedMut = useTriggerFeed()
  const deleteFeed = useDeleteFeed()
  const { toast } = useToast()

  const handleToggle = (enabled: boolean) => {
    updateFeed.mutate(
      { id: feed.id, data: { enabled } },
      {
        onSuccess: () => {
          toast(`${feed.name} ${enabled ? 'enabled' : 'disabled'}`, 'success')
        },
        onError: () => {
          toast(`Failed to update ${feed.name}`, 'error')
        },
      }
    )
  }

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`Delete feed "${feed.name}"? This cannot be undone.`)) return
    deleteFeed.mutate(feed.id, {
      onSuccess: () => {
        toast(`${feed.name} deleted`, 'success')
      },
      onError: () => {
        toast(`Failed to delete ${feed.name}`, 'error')
      },
    })
  }

  const handleTrigger = (e: React.MouseEvent) => {
    e.stopPropagation()
    triggerFeedMut.mutate(feed.id, {
      onSuccess: () => {
        toast(`${feed.name} triggered`, 'success')
      },
      onError: () => {
        toast(`Failed to trigger ${feed.name}`, 'error')
      },
    })
  }

  return (
    <Card className="transition-colors hover:border-border/80">
      <CardContent className="pt-4 pb-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div
            className="flex-1 cursor-pointer"
            onClick={() => setExpanded((p) => !p)}
          >
            <div className="flex items-center gap-2">
              {runStatusIndicator(feed.latest_run?.status ?? null)}
              <h3 className="font-semibold text-foreground">{feed.name}</h3>
              <Badge className={cn('text-[10px]', feedTypeBadge[feed.feed_type])}>
                {feed.feed_type}
              </Badge>
            </div>
            {feed.description && (
              <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                {feed.description}
              </p>
            )}
          </div>
          <Toggle
            checked={feed.enabled}
            onChange={handleToggle}
            disabled={updateFeed.isPending}
          />
        </div>

        {/* Stats row */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>
            <span className="font-medium text-foreground tabular-nums">
              {feed.observable_count.toLocaleString()}
            </span>{' '}
            observables
          </span>
          {feed.schedule_cron && (
            <span className="font-mono">{feed.schedule_cron}</span>
          )}
          {feed.last_run_at && (
            <span>Last run {formatRelativeTime(feed.last_run_at)}</span>
          )}
          <span>Confidence: {feed.default_confidence}</span>
        </div>

        {/* Action buttons */}
        <div className="mt-3 flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTrigger}
            disabled={!feed.enabled || triggerFeedMut.isPending}
          >
            {triggerFeedMut.isPending ? (
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                Running...
              </span>
            ) : (
              'Run Now'
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded((p) => !p)}
          >
            {expanded ? 'Hide Details' : 'Show Details'}
          </Button>
          {!feed.is_preconfigured && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              disabled={deleteFeed.isPending}
            >
              Delete
            </Button>
          )}
        </div>

        {/* Expanded detail */}
        {expanded && (
          <div className="mt-4 border-t border-border pt-4">
            {/* Config info */}
            <div className="mb-4 grid grid-cols-2 gap-2 text-sm">
              {feed.url && (
                <div>
                  <span className="text-muted-foreground">URL:</span>{' '}
                  <span className="font-mono text-xs break-all">{feed.url}</span>
                </div>
              )}
              <div>
                <span className="text-muted-foreground">Type:</span>{' '}
                <span>{feed.feed_type}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Default Confidence:</span>{' '}
                <span>{feed.default_confidence}</span>
              </div>
              {feed.schedule_cron && (
                <div>
                  <span className="text-muted-foreground">Schedule:</span>{' '}
                  <span className="font-mono">{feed.schedule_cron}</span>
                </div>
              )}
            </div>

            {/* Run history */}
            <FeedRunHistory feedId={feed.id} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

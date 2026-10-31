import { useState } from 'react'
import {
  Browser,
  Clock,
  CloudArrowDown,
  DotsThreeVertical,
  FileText,
  Gear,
  Play,
} from '@phosphor-icons/react'
import { useUpdateFeed, useTriggerFeed, useDeleteFeed } from '@/hooks/useFeeds'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Popover } from '@/components/ui/Popover'
import { Toggle } from '@/components/ui/Toggle'
import { apiErrorMessage } from '@/lib/apiError'
import { compactNumber } from '@/lib/dashboardFormat'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { Feed, FeedType } from '@/types/feed'
import { FeedRunHistory } from './FeedRunHistory'

interface FeedCardProps {
  feed: Feed
}

const FEED_TYPE_CONFIG: Record<
  FeedType,
  { Icon: React.ElementType; iconClassName: string; label: string }
> = {
  api: { Icon: CloudArrowDown, iconClassName: 'text-cat-blue', label: 'API' },
  file: { Icon: FileText, iconClassName: 'text-cat-green', label: 'File' },
  scraper: { Icon: Browser, iconClassName: 'text-cat-purple', label: 'Scraper' },
}

function humanizeCron(cron: string): string {
  const everyHours = cron.match(/^0 \*\/(\d+) \* \* \*$/)
  if (everyHours) return `every ${everyHours[1]}h`
  const everyMins = cron.match(/^\*\/(\d+) \* \* \* \*$/)
  if (everyMins) return `every ${everyMins[1]}m`
  if (cron === '0 * * * *') return 'every 1h'
  if (cron === '0 0 * * *') return 'daily'
  return cron
}

function FeedStatus({ feed }: { feed: Feed }) {
  if (!feed.enabled) return <Badge variant="secondary">Disabled</Badge>
  if (feed.latest_run?.status === 'failure') return <Badge variant="destructive">Error</Badge>
  if (feed.latest_run?.status === 'running') return <Badge variant="default">Running</Badge>

  const isStale = !feed.last_run_at
    || Date.now() - new Date(feed.last_run_at).getTime() > 24 * 60 * 60 * 1000
  if (isStale) return <Badge variant="warning">Stale</Badge>
  return <Badge variant="success">OK</Badge>
}

export function FeedCard({ feed }: FeedCardProps) {
  const [showHistory, setShowHistory] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const updateFeed = useUpdateFeed()
  const triggerFeed = useTriggerFeed()
  const deleteFeed = useDeleteFeed()
  const { toast } = useToast()
  const { isAdmin } = useAuth()
  const typeConfig = FEED_TYPE_CONFIG[feed.feed_type]

  const handleToggle = (enabled: boolean) => {
    updateFeed.mutate(
      { id: feed.id, data: { enabled } },
      {
        onSuccess: () => toast(`${feed.name} ${enabled ? 'enabled' : 'disabled'}`, 'success'),
        onError: () => toast(`Failed to update ${feed.name}`, 'error'),
      },
    )
  }

  const handleTrigger = () => {
    triggerFeed.mutate(feed.id, {
      onSuccess: () => toast(`${feed.name} triggered`, 'success'),
      onError: () => toast(`Failed to trigger ${feed.name}`, 'error'),
    })
  }

  const handleDelete = () => {
    deleteFeed.mutate(feed.id, {
      onSuccess: () => {
        toast(`${feed.name} deleted`, 'success')
        setShowDelete(false)
      },
      onError: (error) => {
        toast(apiErrorMessage(error, `Failed to delete ${feed.name}`), 'error')
        setShowDelete(false)
      },
    })
  }

  return (
    <>
      <Card className={cn('transition-colors hover:border-borderStrong', !feed.enabled && 'opacity-75')}>
        <CardContent className="p-4 sm:p-5">
          <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-start">
            <div className="flex min-w-0 flex-1 gap-3 sm:gap-4">
              <div
                aria-hidden="true"
                className={cn(
                  'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surface2',
                  typeConfig.iconClassName,
                )}
              >
                <typeConfig.Icon size={22} weight="duotone" />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold text-foreground">{feed.name}</h3>
                  <Badge variant="outline">{typeConfig.label}</Badge>
                  <FeedStatus feed={feed} />
                </div>
                {feed.description && (
                  <p className="mt-1 text-sm text-muted-foreground">{feed.description}</p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground">
                  <span>
                    <span className="text-foreground">{compactNumber(feed.observable_count)}</span>{' '}
                    observables
                  </span>
                  {feed.schedule_cron && (
                    <span className="flex items-center gap-1">
                      <Clock size={12} aria-hidden="true" />
                      {humanizeCron(feed.schedule_cron)}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Gear size={12} aria-hidden="true" />
                    conf {feed.default_confidence}
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-text3">
                  {feed.last_run_at ? `Last run ${formatRelativeTime(feed.last_run_at)}` : 'No runs recorded'}
                </p>
              </div>
            </div>

            <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
              <Button
                aria-label="Run now"
                variant="outline"
                size="sm"
                onClick={handleTrigger}
                disabled={!isAdmin || !feed.enabled || triggerFeed.isPending}
                title={!isAdmin ? 'Admin only' : undefined}
              >
                <Play size={14} aria-hidden="true" />
                {triggerFeed.isPending ? 'Running…' : 'Run now'}
              </Button>
              <span title={!isAdmin ? 'Admin only' : undefined}>
                <Toggle
                  checked={feed.enabled}
                  onChange={handleToggle}
                  disabled={!isAdmin || updateFeed.isPending}
                  label={feed.enabled ? 'Enabled' : 'Disabled'}
                />
              </span>
              <Popover
                trigger={
                  <button
                    type="button"
                    aria-label="Feed options"
                    className="rounded-lg p-2 text-muted-foreground hover:bg-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    <DotsThreeVertical size={18} aria-hidden="true" />
                  </button>
                }
                align="end"
              >
                <div className="flex flex-col py-0.5">
                  <button
                    type="button"
                    className="rounded-lg px-3 py-2 text-left text-sm hover:bg-hover"
                    onClick={() => setShowHistory((visible) => !visible)}
                  >
                    {showHistory ? 'Hide run history' : 'Show run history'}
                  </button>
                  {isAdmin && !feed.is_preconfigured && (
                    <button
                      type="button"
                      className="rounded-lg px-3 py-2 text-left text-sm text-destructive hover:bg-hover"
                      onClick={() => setShowDelete(true)}
                    >
                      Delete
                    </button>
                  )}
                </div>
              </Popover>
            </div>
          </div>

          {showHistory && (
            <div className="mt-4 border-t border-border pt-4">
              <FeedRunHistory feedId={feed.id} />
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={showDelete} onClose={() => setShowDelete(false)} title="Delete feed">
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Delete <span className="font-medium text-foreground">{feed.name}</span>? This action
            cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowDelete(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteFeed.isPending}>
              {deleteFeed.isPending ? 'Deleting…' : 'Delete feed'}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}

import { useState } from 'react'
import {
  CloudArrowDown,
  FileText,
  Browser,
  Play,
  DotsThreeVertical,
  Clock,
  Gear,
} from '@phosphor-icons/react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { Popover } from '@/components/ui/Popover'
import { FeedRunHistory } from './FeedRunHistory'
import { useUpdateFeed, useTriggerFeed, useDeleteFeed } from '@/hooks/useFeeds'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { cn, formatRelativeTime } from '@/lib/utils'
import { compactNumber } from '@/lib/dashboardFormat'
import type { Feed, FeedRunStatus, FeedType } from '@/types/feed'

// ── Types ────────────────────────────────────────────────────────────────────

interface FeedCardProps {
  feed: Feed
}

// ── Constants ────────────────────────────────────────────────────────────────

const FEED_TYPE_CONFIG: Record<
  FeedType,
  { Icon: React.ElementType; color: string; label: string }
> = {
  api: { Icon: CloudArrowDown, color: 'var(--cat-blue)', label: 'API' },
  file: { Icon: FileText, color: 'var(--cat-green)', label: 'File' },
  scraper: { Icon: Browser, color: 'var(--cat-purple)', label: 'Scraper' },
}

const STATUS_DISPLAY: Record<FeedRunStatus, string> = {
  success: 'Success',
  failure: 'Failed',
  running: 'Running',
}

// ── Helpers ──────────────────────────────────────────────────────────────────

// Humanize common cron expressions; falls back to raw string.
function humanizeCron(cron: string): string {
  const everyHours = cron.match(/^0 \*\/(\d+) \* \* \*$/)
  if (everyHours) return `every ${everyHours[1]}h`
  const everyMins = cron.match(/^\*\/(\d+) \* \* \* \*$/)
  if (everyMins) return `every ${everyMins[1]}m`
  if (cron === '0 * * * *') return 'every 1h'
  if (cron === '0 0 * * *') return 'daily'
  return cron
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatusDot({ status }: { status: FeedRunStatus | null | undefined }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-block h-2 w-2 shrink-0 rounded-full',
        !status
          ? 'bg-muted-foreground'
          : status === 'success'
            ? 'bg-cat-green'
            : status === 'failure'
              ? 'bg-conf-critical'
              : 'bg-cat-blue animate-pulse-dot',
      )}
    />
  )
}

// ── Component ────────────────────────────────────────────────────────────────

export function FeedCard({ feed }: FeedCardProps) {
  const [showHistory, setShowHistory] = useState(false)

  const updateFeed = useUpdateFeed()
  const triggerFeedMut = useTriggerFeed()
  const deleteFeed = useDeleteFeed()
  const { toast } = useToast()
  const { isAdmin } = useAuth()

  const typeConfig = FEED_TYPE_CONFIG[feed.feed_type]
  const { Icon } = typeConfig
  const runStatus = feed.latest_run?.status

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleToggle = (newEnabled: boolean) => {
    updateFeed.mutate(
      { id: feed.id, data: { enabled: newEnabled } },
      {
        onSuccess: () =>
          toast(`${feed.name} ${newEnabled ? 'enabled' : 'disabled'}`, 'success'),
        onError: () => toast(`Failed to update ${feed.name}`, 'error'),
      },
    )
  }

  const handleTrigger = (e: React.MouseEvent) => {
    e.stopPropagation()
    triggerFeedMut.mutate(feed.id, {
      onSuccess: () => toast(`${feed.name} triggered`, 'success'),
      onError: () => toast(`Failed to trigger ${feed.name}`, 'error'),
    })
  }

  const handleDelete = () => {
    if (!window.confirm(`Delete feed "${feed.name}"? This cannot be undone.`)) return
    deleteFeed.mutate(feed.id, {
      onSuccess: () => toast(`${feed.name} deleted`, 'success'),
      onError: () => toast(`Failed to delete ${feed.name}`, 'error'),
    })
  }

  // ── Status line color ────────────────────────────────────────────────────
  const statusLineColor =
    !runStatus
      ? 'text-muted-foreground'
      : runStatus === 'success'
        ? 'text-cat-green'
        : runStatus === 'failure'
          ? 'text-conf-critical'
          : 'text-cat-blue'

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <Card
      className={cn(
        'transition-colors hover:border-border/80',
        !feed.enabled && 'opacity-60',
      )}
    >
      <CardContent className="py-4">
        <div className="flex items-center gap-4">
          {/* ── Type icon tile ───────────────────────────────────────────── */}
          <div
            aria-hidden="true"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg"
            style={{
              backgroundColor: `color-mix(in srgb, ${typeConfig.color} 15%, transparent)`,
              color: typeConfig.color,
            }}
          >
            <Icon size={22} weight="duotone" />
          </div>

          {/* ── Main body ────────────────────────────────────────────────── */}
          <div className="min-w-0 flex-1">
            {/* Header row: status dot · name · type chip */}
            <div className="flex items-center gap-2">
              <StatusDot status={runStatus} />
              <span className="font-semibold text-foreground">{feed.name}</span>
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                style={{
                  backgroundColor: `color-mix(in srgb, ${typeConfig.color} 15%, transparent)`,
                  color: typeConfig.color,
                }}
              >
                {typeConfig.label}
              </span>
            </div>

            {/* Description */}
            {feed.description && (
              <p className="mt-0.5 line-clamp-1 text-sm text-muted-foreground">
                {feed.description}
              </p>
            )}

            {/* Meta row: observables · schedule · confidence */}
            <div className="mt-1 flex flex-wrap items-center gap-x-3 font-mono text-xs text-muted-foreground">
              <span>
                <span className="text-foreground">{compactNumber(feed.observable_count)}</span>
                {' '}observables
              </span>
              {feed.schedule_cron && (
                <span className="flex items-center gap-1">
                  <Clock size={11} aria-hidden="true" />
                  {humanizeCron(feed.schedule_cron)}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Gear size={11} aria-hidden="true" />
                conf {feed.default_confidence}
              </span>
            </div>

            {/* Status line */}
            {(runStatus || feed.last_run_at) && (
              <div className={cn('mt-0.5 text-xs font-medium', statusLineColor)}>
                {runStatus ? STATUS_DISPLAY[runStatus] : 'No status'} ·{' '}
                {formatRelativeTime(feed.last_run_at)}
              </div>
            )}
          </div>

          {/* ── Right-side actions ───────────────────────────────────────── */}
          <div className="flex shrink-0 items-center gap-2">
            <Button
              aria-label="Run now"
              variant="outline"
              size="sm"
              onClick={handleTrigger}
              disabled={!feed.enabled || triggerFeedMut.isPending}
            >
              <Play size={14} aria-hidden="true" />
              {triggerFeedMut.isPending ? 'Running…' : 'Run now'}
            </Button>

            <Toggle
              checked={feed.enabled}
              onChange={handleToggle}
              disabled={updateFeed.isPending}
            />

            <Popover
              trigger={
                <button
                  type="button"
                  aria-label="Feed options"
                  className="rounded p-1 text-muted-foreground hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <DotsThreeVertical size={18} aria-hidden="true" />
                </button>
              }
              align="end"
            >
              <div className="flex flex-col py-0.5">
                <button
                  type="button"
                  className="rounded px-3 py-1.5 text-left text-sm hover:bg-hover"
                  onClick={() => setShowHistory((p) => !p)}
                >
                  {showHistory ? 'Hide run history' : 'Show run history'}
                </button>
                {isAdmin && !feed.is_preconfigured && (
                  <button
                    type="button"
                    className="rounded px-3 py-1.5 text-left text-sm text-conf-critical hover:bg-hover"
                    onClick={handleDelete}
                  >
                    Delete
                  </button>
                )}
              </div>
            </Popover>
          </div>
        </div>

        {/* Run history (toggles via overflow menu) */}
        {showHistory && (
          <div className="mt-4 border-t border-border pt-4">
            <FeedRunHistory feedId={feed.id} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

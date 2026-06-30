import { useState } from 'react'
import { Plus } from '@phosphor-icons/react'
import { useFeeds, useCreateFeed } from '@/hooks/useFeeds'
import { useDashboard } from '@/hooks/useDashboard'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { FeedCard } from '@/components/feeds/FeedCard'
import { FeedForm } from '@/components/feeds/FeedForm'
import { compactNumber } from '@/lib/dashboardFormat'
import { cn } from '@/lib/utils'
import type { FeedCreate, FeedType } from '@/types/feed'

// ── Types ────────────────────────────────────────────────────────────────────

type FilterSegment = 'all' | FeedType

// ── Constants ────────────────────────────────────────────────────────────────

const SEGMENTS: { key: FilterSegment; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'api', label: 'API' },
  { key: 'file', label: 'File' },
  { key: 'scraper', label: 'Scraper' },
]

// ── Sub-components ───────────────────────────────────────────────────────────

interface SummaryCardProps {
  label: string
  value: string | number
  valueClassName?: string
}

function SummaryCard({ label, value, valueClassName }: SummaryCardProps) {
  return (
    <Card>
      <CardContent className="px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p
          className={cn(
            'mt-1.5 font-mono text-2xl font-semibold tabular-nums',
            valueClassName,
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function FeedsPage() {
  const { data: feeds, isLoading: feedsLoading, error: feedsError } = useFeeds()
  const { data: stats } = useDashboard()
  const createFeed = useCreateFeed()
  const { toast } = useToast()
  const { isAdmin } = useAuth()

  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [activeSegment, setActiveSegment] = useState<FilterSegment>('all')

  const handleCreate = (data: FeedCreate) => {
    createFeed.mutate(data, {
      onSuccess: () => {
        toast('Feed created successfully', 'success')
        setShowCreateDialog(false)
      },
      onError: (err) => {
        toast(
          err instanceof Error ? err.message : 'Failed to create feed',
          'error',
        )
      },
    })
  }

  if (feedsLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (feedsError) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-destructive-foreground">Failed to load feeds</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {feedsError instanceof Error ? feedsError.message : 'Unknown error'}
        </p>
      </div>
    )
  }

  const allFeeds = feeds ?? []
  const configuredCount = allFeeds.length
  const enabledCount = allFeeds.filter((f) => f.enabled).length
  const errorCount = stats?.feed_errors_24h ?? 0
  const totalObservables = stats?.total_observables ?? 0

  const filteredFeeds =
    activeSegment === 'all'
      ? allFeeds
      : allFeeds.filter((f) => f.feed_type === activeSegment)

  return (
    <div className="space-y-3.5">
      {/* ── Summary cards ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3.5">
        <SummaryCard label="Configured feeds" value={configuredCount} />
        <SummaryCard
          label="Enabled"
          value={enabledCount}
          valueClassName="text-cat-green"
        />
        <SummaryCard
          label="Errors (24h)"
          value={errorCount}
          valueClassName="text-conf-critical"
        />
      </div>

      {/* Observables wide card */}
      <Card>
        <CardContent className="px-5 py-4">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Observables
          </p>
          <p
            className="mt-1.5 font-mono text-2xl font-semibold tabular-nums"
            style={{ color: 'var(--brand)' }}
          >
            {compactNumber(totalObservables)}
          </p>
        </CardContent>
      </Card>

      {/* ── Toolbar: segmented filter + Add Feed ────────────────────────── */}
      <div className="flex items-center justify-between gap-3">
        {/* Segmented control */}
        <div
          className="flex items-center gap-0.5 rounded-md border border-border bg-surface-2 p-0.5"
          role="group"
          aria-label="Filter feeds by type"
        >
          {SEGMENTS.map(({ key, label }) => {
            const isActive = activeSegment === key
            return (
              <button
                key={key}
                type="button"
                aria-pressed={isActive}
                onClick={() => setActiveSegment(key)}
                className={cn(
                  'rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive
                    ? 'text-brand'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                style={
                  isActive
                    ? {
                        backgroundColor:
                          'color-mix(in srgb, var(--brand) 13%, transparent)',
                      }
                    : undefined
                }
              >
                {label}
              </button>
            )
          })}
        </div>

        {/* Add Feed button — admin only */}
        {isAdmin && (
          <Button variant="brand" onClick={() => setShowCreateDialog(true)}>
            <Plus size={16} weight="bold" aria-hidden="true" className="mr-1.5" />
            Add Feed
          </Button>
        )}
      </div>

      {/* ── Feed list ────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3.5">
        {filteredFeeds.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {activeSegment === 'all'
              ? 'No feeds configured yet.'
              : `No ${activeSegment} feeds.`}
          </p>
        ) : (
          filteredFeeds.map((feed) => <FeedCard key={feed.id} feed={feed} />)
        )}
      </div>

      {/* ── Create dialog ────────────────────────────────────────────────── */}
      <Dialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        title="Add Feed"
      >
        <FeedForm
          onSubmit={handleCreate}
          onCancel={() => setShowCreateDialog(false)}
          isLoading={createFeed.isPending}
        />
      </Dialog>
    </div>
  )
}

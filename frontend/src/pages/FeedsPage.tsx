import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus } from '@phosphor-icons/react'
import { useFeeds, useCreateFeed, useUpdateFeed } from '@/hooks/useFeeds'
import { useDashboard } from '@/hooks/useDashboard'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Tabs } from '@/components/ui/Tabs'
import { FeedCard } from '@/components/feeds/FeedCard'
import { FeedForm } from '@/components/feeds/FeedForm'
import { apiErrorMessage } from '@/lib/apiError'
import { compactNumber } from '@/lib/dashboardFormat'
import { cn } from '@/lib/utils'
import type { Feed, FeedCreate, FeedUpdate, FeedType } from '@/types/feed'

type FilterSegment = 'all' | FeedType

const SEGMENTS: { key: FilterSegment; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'api', label: 'API' },
  { key: 'file', label: 'File' },
  { key: 'scraper', label: 'Scraper' },
]

interface SummaryCardProps {
  label: string
  value: string | number
  valueClassName?: string
}

function SummaryCard({ label, value, valueClassName }: SummaryCardProps) {
  return (
    <div className="rounded-xl bg-surface2 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={cn(
          'mt-1.5 font-mono text-2xl font-semibold tabular-nums text-foreground',
          valueClassName,
        )}
      >
        {value}
      </p>
    </div>
  )
}

export default function FeedsPage() {
  const { data: feeds, isLoading: feedsLoading, error: feedsError } = useFeeds()
  const { data: stats } = useDashboard()
  const createFeed = useCreateFeed()
  const updateFeed = useUpdateFeed()
  const { toast } = useToast()
  const { isAdmin } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeSegment, setActiveSegment] = useState<FilterSegment>('all')
  const [editingFeed, setEditingFeed] = useState<Feed | null>(null)
  const [editSubmitError, setEditSubmitError] = useState<string | null>(null)
  const showCreateDialog = isAdmin && searchParams.get('create') === '1'
  const highlightFeedId = searchParams.get('feed')

  useEffect(() => {
    if (!highlightFeedId || feedsLoading) return
    const el = document.getElementById(`feed-${highlightFeedId}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [highlightFeedId, feedsLoading, feeds])

  const openCreateDialog = () => {
    const params = new URLSearchParams(searchParams)
    params.set('create', '1')
    setSearchParams(params)
  }

  const closeCreateDialog = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('create')
    setSearchParams(params, { replace: true })
  }

  const handleCreate = (data: FeedCreate) => {
    createFeed.mutate(data, {
      onSuccess: () => {
        toast('Feed created successfully', 'success')
        closeCreateDialog()
      },
      onError: (err) => {
        toast(err instanceof Error ? err.message : 'Failed to create feed', 'error')
      },
    })
  }

  const handleEdit = (data: FeedUpdate) => {
    if (!editingFeed) return
    setEditSubmitError(null)
    updateFeed.mutate(
      { id: editingFeed.id, data },
      {
        onSuccess: () => {
          toast('Feed updated', 'success')
          setEditingFeed(null)
          setEditSubmitError(null)
        },
        onError: (err) => {
          const message = apiErrorMessage(err, 'Failed to update feed')
          setEditSubmitError(message)
          toast(message, 'error')
        },
      },
    )
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
        <p role="alert" className="text-destructive">Failed to load feeds</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {feedsError instanceof Error ? feedsError.message : 'Unknown error'}
        </p>
      </div>
    )
  }

  const allFeeds = feeds ?? []
  const configuredCount = allFeeds.length
  const enabledCount = allFeeds.filter((feed) => feed.enabled).length
  const errorCount = stats?.feed_errors_24h ?? 0
  const totalObservables = stats?.total_observables ?? 0
  const filteredFeeds = activeSegment === 'all'
    ? allFeeds
    : allFeeds.filter((feed) => feed.feed_type === activeSegment)

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4 sm:p-5">
          <SummaryCard label="Configured feeds" value={configuredCount} />
          <SummaryCard label="Enabled" value={enabledCount} valueClassName="text-success" />
          <SummaryCard label="Errors (24h)" value={errorCount} valueClassName="text-destructive" />
          <SummaryCard
            label="Observables"
            value={compactNumber(totalObservables)}
            valueClassName="text-primary"
          />
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <Tabs
          tabs={SEGMENTS}
          active={activeSegment}
          onChange={(key) => setActiveSegment(key as FilterSegment)}
          className="min-w-0 flex-1 sm:max-w-md"
        />
        {isAdmin && (
          <Button variant="brand" onClick={openCreateDialog} className="self-start sm:self-auto">
            <Plus size={16} weight="bold" aria-hidden="true" />
            Add Feed
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-4">
        {filteredFeeds.length === 0 ? (
          <Card>
            <EmptyState
              title={activeSegment === 'all'
                ? 'No feeds configured'
                : `No ${SEGMENTS.find((segment) => segment.key === activeSegment)?.label ?? activeSegment} feeds`}
              description={activeSegment === 'all'
                ? 'Add a feed to begin ingesting threat intelligence.'
                : 'Choose another feed type or add a new feed.'}
            >
              {isAdmin && activeSegment === 'all' && (
                <Button onClick={openCreateDialog}>
                  <Plus size={16} weight="bold" aria-hidden="true" />
                  Add Feed
                </Button>
              )}
            </EmptyState>
          </Card>
        ) : (
          filteredFeeds.map((feed) => (
            <FeedCard
              key={feed.id}
              feed={feed}
              highlighted={highlightFeedId === feed.id}
              onEdit={(feed) => {
              setEditSubmitError(null)
              setEditingFeed(feed)
            }} />
          ))
        )}
      </div>

      <Dialog open={showCreateDialog} onClose={closeCreateDialog} title="Add Feed">
        <FeedForm
          onSubmit={handleCreate}
          onCancel={closeCreateDialog}
          isLoading={createFeed.isPending}
        />
      </Dialog>

      {/* ── Edit dialog ──────────────────────────────────────────────────── */}
      {editingFeed && (
        <Dialog open onClose={() => { setEditingFeed(null); setEditSubmitError(null) }} title="Edit Feed">
          <FeedForm
            initialValues={editingFeed}
            onSubmit={handleEdit}
            onCancel={() => { setEditingFeed(null); setEditSubmitError(null) }}
            isLoading={updateFeed.isPending}
            submitError={editSubmitError}
          />
        </Dialog>
      )}
    </div>
  )
}

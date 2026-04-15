import { useState } from 'react'
import { useFeeds, useCreateFeed } from '@/hooks/useFeeds'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { FeedCard } from '@/components/feeds/FeedCard'
import { FeedForm } from '@/components/feeds/FeedForm'
import type { FeedCreate } from '@/types/feed'

export default function FeedsPage() {
  const { data: feeds, isLoading, error } = useFeeds()
  const createFeed = useCreateFeed()
  const { toast } = useToast()
  const { isAdmin } = useAuth()
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  const handleCreate = (data: FeedCreate) => {
    createFeed.mutate(data, {
      onSuccess: () => {
        toast('Feed created successfully', 'success')
        setShowCreateDialog(false)
      },
      onError: (err) => {
        toast(
          err instanceof Error ? err.message : 'Failed to create feed',
          'error'
        )
      },
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-destructive-foreground">Failed to load feeds</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {error instanceof Error ? error.message : 'Unknown error'}
        </p>
      </div>
    )
  }

  const preconfigured = (feeds || []).filter((f) => f.is_preconfigured)
  const custom = (feeds || []).filter((f) => !f.is_preconfigured)

  return (
    <div className="space-y-6">
      {/* Header with create button */}
      {isAdmin && (
        <div className="flex items-center justify-between">
          <div />
          <Button onClick={() => setShowCreateDialog(true)}>
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              className="mr-1.5"
            >
              <line x1="8" y1="3" x2="8" y2="13" />
              <line x1="3" y1="8" x2="13" y2="8" />
            </svg>
            Add Custom Feed
          </Button>
        </div>
      )}

      {/* Pre-configured feeds */}
      {preconfigured.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
            Pre-configured Feeds ({preconfigured.length})
          </h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {preconfigured.map((feed) => (
              <FeedCard key={feed.id} feed={feed} />
            ))}
          </div>
        </section>
      )}

      {/* Custom feeds */}
      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Custom Feeds ({custom.length})
        </h2>
        {custom.length === 0 ? (
          <EmptyState
            title="No custom feeds"
            description="Add a custom feed to start ingesting observables from your own sources"
          >
            {isAdmin && (
              <Button variant="outline" onClick={() => setShowCreateDialog(true)}>
                Add Custom Feed
              </Button>
            )}
          </EmptyState>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {custom.map((feed) => (
              <FeedCard key={feed.id} feed={feed} />
            ))}
          </div>
        )}
      </section>

      {/* Create feed dialog */}
      <Dialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        title="Add Custom Feed"
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

import { useState } from 'react';
import {
  useFeeds,
  useCreateFeed,
  useUpdateFeed,
  useDeleteFeed,
  useTriggerFeed,
  useFeedRuns,
  useBulkUpdateFeeds,
  useBulkDeleteFeeds,
  useBulkTriggerFeeds,
} from '@/hooks/useFeeds';
import { useAuth } from '@/hooks/useAuth';
import { canManageFeeds, canTriggerFeed } from '@/lib/permissions';
import { FeedCard } from '@/components/feeds/FeedCard';
import { FeedForm } from '@/components/feeds/FeedForm';
import { FeedRunHistory } from '@/components/feeds/FeedRunHistory';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import type { FeedResponse, FeedCreateRequest } from '@/types/feed';

export function FeedsPage() {
  const { data: feeds, isLoading } = useFeeds();
  const { user } = useAuth();
  const createMutation = useCreateFeed();
  const updateMutation = useUpdateFeed();
  const deleteMutation = useDeleteFeed();
  const triggerMutation = useTriggerFeed();
  const bulkUpdateMutation = useBulkUpdateFeeds();
  const bulkDeleteMutation = useBulkDeleteFeeds();
  const bulkTriggerMutation = useBulkTriggerFeeds();
  const [selectedFeedIds, setSelectedFeedIds] = useState<Set<string>>(new Set());

  const toggleFeedSelect = (id: string) => {
    setSelectedFeedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const [formOpen, setFormOpen] = useState(false);
  const [editingFeed, setEditingFeed] = useState<FeedResponse | null>(null);
  const [historyFeedId, setHistoryFeedId] = useState<string | null>(null);

  const { data: runs, isLoading: runsLoading } = useFeedRuns(
    historyFeedId || ''
  );

  const handleCreate = (data: FeedCreateRequest) => {
    if (editingFeed) {
      updateMutation.mutate(
        { id: editingFeed.id, data },
        {
          onSuccess: () => {
            setFormOpen(false);
            setEditingFeed(null);
          },
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => {
          setFormOpen(false);
        },
      });
    }
  };

  const handleEdit = (feed: FeedResponse) => {
    setEditingFeed(feed);
    setFormOpen(true);
  };

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this feed?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleFormClose = (open: boolean) => {
    setFormOpen(open);
    if (!open) {
      setEditingFeed(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Feeds</h1>
          <p className="text-muted-foreground">
            {feeds?.length || 0} feed connectors configured
          </p>
        </div>
        {canManageFeeds(user) && (
          <Button onClick={() => setFormOpen(true)}>+ Add Feed</Button>
        )}
      </div>

      {selectedFeedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-3">
          <span className="text-sm font-medium">{selectedFeedIds.size} selected</span>
          <div className="h-4 w-px bg-border" />
          {canManageFeeds(user) && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  bulkUpdateMutation.mutate(
                    { ids: Array.from(selectedFeedIds), updates: { enabled: true } },
                    { onSuccess: () => setSelectedFeedIds(new Set()) }
                  );
                }}
                disabled={bulkUpdateMutation.isPending}
              >
                Enable All
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  bulkUpdateMutation.mutate(
                    { ids: Array.from(selectedFeedIds), updates: { enabled: false } },
                    { onSuccess: () => setSelectedFeedIds(new Set()) }
                  );
                }}
                disabled={bulkUpdateMutation.isPending}
              >
                Disable All
              </Button>
            </>
          )}
          {canTriggerFeed(user) && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                bulkTriggerMutation.mutate(Array.from(selectedFeedIds), {
                  onSuccess: () => setSelectedFeedIds(new Set()),
                });
              }}
              disabled={bulkTriggerMutation.isPending}
            >
              {bulkTriggerMutation.isPending ? 'Triggering...' : 'Trigger Selected'}
            </Button>
          )}
          {canManageFeeds(user) && (
            <Button
              size="sm"
              variant="destructive"
              onClick={() => {
                if (window.confirm(`Delete ${selectedFeedIds.size} feeds?`)) {
                  bulkDeleteMutation.mutate(Array.from(selectedFeedIds), {
                    onSuccess: () => setSelectedFeedIds(new Set()),
                  });
                }
              }}
              disabled={bulkDeleteMutation.isPending}
            >
              Delete Selected
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setSelectedFeedIds(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {feeds && feeds.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {feeds.map((feed) => (
            <div key={feed.id} className="relative">
              <div className="absolute top-3 left-3 z-10" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-input bg-background"
                  checked={selectedFeedIds.has(feed.id)}
                  onChange={() => toggleFeedSelect(feed.id)}
                />
              </div>
              <FeedCard
                feed={feed}
                onTrigger={(id) => triggerMutation.mutate(id)}
                onEdit={handleEdit}
                onDelete={handleDelete}
                isTriggering={
                  triggerMutation.isPending &&
                  triggerMutation.variables === feed.id
                }
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <span className="text-4xl mb-3">{'\u21BB'}</span>
          <p className="text-lg font-medium">No feeds configured</p>
          <p className="text-sm mb-4">
            Add a feed connector to start ingesting threat intelligence
          </p>
          {canManageFeeds(user) && (
            <Button onClick={() => setFormOpen(true)}>Add First Feed</Button>
          )}
        </div>
      )}

      {/* Feed Run History for any feed - accessible via clicking feed cards */}
      {feeds && feeds.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">Run History</h2>
            <select
              className="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
              value={historyFeedId || ''}
              onChange={(e) => setHistoryFeedId(e.target.value || null)}
            >
              <option value="">Select a feed...</option>
              {feeds.map((feed) => (
                <option key={feed.id} value={feed.id}>
                  {feed.name}
                </option>
              ))}
            </select>
          </div>
          {historyFeedId && (
            <FeedRunHistory runs={runs || []} isLoading={runsLoading} />
          )}
        </div>
      )}

      {/* Feed Form Dialog */}
      <FeedForm
        open={formOpen}
        onOpenChange={handleFormClose}
        onSubmit={handleCreate}
        initialData={editingFeed}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
      />
    </div>
  );
}

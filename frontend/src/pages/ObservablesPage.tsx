import { useState } from 'react'
import { SortAscending, SortDescending } from '@phosphor-icons/react'
import { useObservables, useCreateObservable } from '@/hooks/useObservables'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { Dialog } from '@/components/ui/Dialog'
import { ObservableFilters } from '@/components/observables/ObservableFilters'
import { ObservableTable } from '@/components/observables/ObservableTable'
import { ObservableForm } from '@/components/observables/ObservableForm'
import type { ObservableFilters as Filters, ObservableCreate } from '@/types/observable'

const SORT_OPTIONS = [
  { value: 'last_seen', label: 'Last seen' },
  { value: 'confidence_score', label: 'Confidence' },
  { value: 'first_seen', label: 'First seen' },
  { value: 'value', label: 'Value' },
]

export default function ObservablesPage() {
  const [filters, setFilters] = useState<Filters>({
    page: 1,
    size: 10,
    sort: 'last_seen',
    order: 'desc',
  })
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  const { data, isLoading, error } = useObservables(filters)
  const createObservable = useCreateObservable()
  const { toast } = useToast()
  const { isAdmin } = useAuth()

  /** Update filter fields and reset to page 1 */
  const updateFilters = (partial: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...partial, page: 1 }))
  }

  const handleCreate = (payload: ObservableCreate) => {
    createObservable.mutate(payload, {
      onSuccess: () => {
        toast('Observable added successfully', 'success')
        setShowCreateDialog(false)
      },
      onError: (err) => {
        toast(
          err instanceof Error ? err.message : 'Failed to add observable',
          'error',
        )
      },
    })
  }

  return (
    <div className="space-y-4">
      {/* ── Filter toolbar ─────────────────────────────────────────── */}
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <ObservableFilters filters={filters} onChange={setFilters} />
        </div>
        {isAdmin && (
          <Button
            onClick={() => setShowCreateDialog(true)}
            className="mt-0 shrink-0 self-start h-9"
          >
            Add Observable
          </Button>
        )}
      </div>

      {/* ── Results card ───────────────────────────────────────────── */}
      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <LoadingSpinner size="lg" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <p className="text-destructive-foreground">Failed to load observables</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      ) : (
        <>
          <Card>
            {/* Card header: count (left) + sort controls (right) */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="font-mono text-sm font-semibold tabular-nums">
                {data?.total ?? 0} observables
              </span>

              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground select-none">Sort</span>
                <Select
                  aria-label="Sort"
                  options={SORT_OPTIONS}
                  value={filters.sort ?? 'last_seen'}
                  onChange={(e) => updateFilters({ sort: e.target.value })}
                  className="w-36 h-8 text-xs"
                />
                <button
                  type="button"
                  aria-label="Toggle sort order"
                  onClick={() =>
                    updateFilters({ order: filters.order === 'asc' ? 'desc' : 'asc' })
                  }
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-input bg-background text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {filters.order === 'asc' ? (
                    <SortAscending size={16} weight="bold" />
                  ) : (
                    <SortDescending size={16} weight="bold" />
                  )}
                </button>
              </div>
            </div>

            {/* Table or empty state */}
            <CardContent className="p-0">
              {!data || data.items.length === 0 ? (
                <div className="py-6">
                  <EmptyState
                    title="No observables found"
                    description={
                      filters.q || filters.type || filters.confidence_min
                        ? 'Try adjusting your filters'
                        : 'Observables will appear here once feeds start ingesting data'
                    }
                  />
                </div>
              ) : (
                <ObservableTable observables={data.items} />
              )}
            </CardContent>
          </Card>

          {/* Pagination */}
          {data && (
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
            />
          )}
        </>
      )}

      {/* ── Create observable dialog ───────────────────────────────── */}
      <Dialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        title="Add Observable"
      >
        <ObservableForm
          onSubmit={handleCreate}
          onCancel={() => setShowCreateDialog(false)}
          isLoading={createObservable.isPending}
        />
      </Dialog>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SortAscending, SortDescending } from '@phosphor-icons/react'
import { useObservables, useCreateObservable } from '@/hooks/useObservables'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
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
    q: undefined,
  })
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  const { data, isLoading, error } = useObservables(filters)
  const createObservable = useCreateObservable()
  const { toast } = useToast()
  const { isAdmin } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()

  // The page-header "Add Observable" button routes here with ?create=1 — open the
  // create dialog once (admin only), then strip the param so it doesn't re-fire.
  useEffect(() => {
    const query = searchParams.get('q')?.trim() || undefined
    setFilters((current) =>
      current.q === query ? current : { ...current, q: query, page: 1 },
    )

    if (searchParams.get('create') === '1') {
      if (isAdmin) setShowCreateDialog(true)
      const next = new URLSearchParams(searchParams)
      next.delete('create')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, isAdmin, setSearchParams])

  const handleFilterChange = (next: Filters) => {
    setFilters(next)
    const params = new URLSearchParams(searchParams)
    if (next.q) params.set('q', next.q)
    else params.delete('q')
    setSearchParams(params, { replace: true })
  }

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
      {/* Admins add observables from the page-header "Add Observable" button. */}
      <ObservableFilters filters={filters} onChange={handleFilterChange} />

      {/* ── Results card ───────────────────────────────────────────── */}
      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <LoadingSpinner size="lg" />
        </div>
      ) : error ? (
        <EmptyState
          className="[&_h3]:text-destructive"
          title="Failed to load observables"
          description={error instanceof Error ? error.message : 'Unknown error'}
        />
      ) : (
        <>
          <Card>
            {/* Card header: count (left) + sort controls (right) */}
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-3 border-b border-border py-4">
              <CardTitle className="font-mono text-sm tabular-nums">
                {data?.total ?? 0} observables
              </CardTitle>

              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-muted-foreground select-none">Sort</span>
                <Select
                  aria-label="Sort"
                  options={SORT_OPTIONS}
                  value={filters.sort ?? 'last_seen'}
                  onChange={(e) => updateFilters({ sort: e.target.value })}
                  className="h-9 w-36 text-xs"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="default"
                  aria-label="Toggle sort order"
                  onClick={() =>
                    updateFilters({ order: filters.order === 'asc' ? 'desc' : 'asc' })
                  }
                  className="w-9 px-0 text-muted-foreground"
                >
                  {filters.order === 'asc' ? (
                    <SortAscending size={16} weight="bold" />
                  ) : (
                    <SortDescending size={16} weight="bold" />
                  )}
                </Button>
              </div>
            </CardHeader>

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

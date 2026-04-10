import { useState } from 'react'
import { useObservables, useCreateObservable } from '@/hooks/useObservables'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ObservableFilters } from '@/components/observables/ObservableFilters'
import { ObservableTable } from '@/components/observables/ObservableTable'
import { ObservableForm } from '@/components/observables/ObservableForm'
import type { ObservableFilters as Filters, ObservableCreate } from '@/types/observable'

export default function ObservablesPage() {
  const [filters, setFilters] = useState<Filters>({
    page: 1,
    size: 50,
    sort: 'last_seen',
    order: 'desc',
  })
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  const { data, isLoading, error } = useObservables(filters)
  const createObservable = useCreateObservable()
  const { toast } = useToast()
  const { isAdmin } = useAuth()

  const handleCreate = (data: ObservableCreate) => {
    createObservable.mutate(data, {
      onSuccess: () => {
        toast('Observable added successfully', 'success')
        setShowCreateDialog(false)
      },
      onError: (err) => {
        toast(
          err instanceof Error ? err.message : 'Failed to add observable',
          'error'
        )
      },
    })
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <ObservableFilters filters={filters} onChange={setFilters} />
            </div>
            {isAdmin && (
              <Button onClick={() => setShowCreateDialog(true)}>
                Add Observable
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

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
      ) : !data || data.items.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <EmptyState
              title="No observables found"
              description={
                filters.q || filters.type || filters.confidence_min
                  ? 'Try adjusting your filters'
                  : 'Observables will appear here once feeds start ingesting data'
              }
            />
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardContent className="p-0">
              <ObservableTable observables={data.items} />
            </CardContent>
          </Card>

          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
          />
        </>
      )}

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

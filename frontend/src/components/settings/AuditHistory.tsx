import { useMemo, useState } from 'react'
import {
  auditOutcomeBadgeVariant,
  auditOutcomeLabel,
  formatAuditSummaryEntries,
  type AuditEvent,
  type AuditEventFilters,
  type AuditOutcome,
} from '@/api/audit'
import { useAuditEvents, useAuditMeta } from '@/hooks/useAudit'
import { apiErrorMessage } from '@/lib/apiError'
import { formatDate } from '@/lib/utils'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Pagination } from '@/components/common/Pagination'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'

const DEFAULT_SIZE = 50

function formatActor(event: AuditEvent): string {
  const label = event.actor_label?.trim()
  if (label) return `${label} (${event.actor_type})`
  if (event.actor_id) return `${event.actor_id} (${event.actor_type})`
  return event.actor_type
}

function formatResource(event: AuditEvent): string {
  const label = event.resource_label?.trim()
  if (label) return `${label} · ${event.resource_type}`
  if (event.resource_id) return `${event.resource_id} · ${event.resource_type}`
  return event.resource_type
}

function datetimeLocalToIso(value: string): string | undefined {
  if (!value) return undefined
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return undefined
  return d.toISOString()
}

export function AuditHistory() {
  const [filters, setFilters] = useState<AuditEventFilters>({ page: 1, size: DEFAULT_SIZE })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sinceLocal, setSinceLocal] = useState('')
  const [untilLocal, setUntilLocal] = useState('')
  const [selectedActions, setSelectedActions] = useState<string[]>([])
  const [selectedOutcomes, setSelectedOutcomes] = useState<string[]>([])

  const { data: meta } = useAuditMeta()

  const effectiveFilters = useMemo((): AuditEventFilters => {
    return {
      ...filters,
      since: datetimeLocalToIso(sinceLocal),
      until: datetimeLocalToIso(untilLocal),
      action: selectedActions.length > 0 ? selectedActions : undefined,
      outcome: selectedOutcomes.length > 0 ? selectedOutcomes : undefined,
    }
  }, [filters, sinceLocal, untilLocal, selectedActions, selectedOutcomes])

  const { data, isLoading, error } = useAuditEvents(effectiveFilters)

  const selectedEvent = data?.items.find((item) => item.id === selectedId) ?? null

  const updateFilters = (partial: Partial<AuditEventFilters>) => {
    setFilters((prev) => ({ ...prev, ...partial, page: 1 }))
    setSelectedId(null)
  }

  const actionOptions = meta?.actions.map((a) => ({ value: a, label: a })) ?? []
  const actorTypeOptions =
    meta?.actor_types.map((t) => ({ value: t, label: t })) ??
    [
      { value: 'user', label: 'user' },
      { value: 'api_key', label: 'api_key' },
      { value: 'system', label: 'system' },
    ]
  const resourceTypeOptions = meta?.resource_types.map((t) => ({ value: t, label: t })) ?? []
  const outcomeOptions =
    meta?.outcomes.map((o) => ({ value: o, label: o })) ??
    (['succeeded', 'failed', 'denied', 'initiated', 'completed', 'interrupted'] as AuditOutcome[]).map(
      (o) => ({ value: o, label: o }),
    )

  const handleActionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedActions(Array.from(e.target.selectedOptions).map((o) => o.value))
    setFilters((prev) => ({ ...prev, page: 1 }))
    setSelectedId(null)
  }

  const handleOutcomeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedOutcomes(Array.from(e.target.selectedOptions).map((o) => o.value))
    setFilters((prev) => ({ ...prev, page: 1 }))
    setSelectedId(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">Audit history</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Admin-only log of sensitive changes and disclosures. Events older than{' '}
          {meta?.retention_days ?? '…'} days are removed automatically.
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          An outcome of <span className="font-medium">initiated</span> without a matching{' '}
          <span className="font-medium">completed</span> event means delivery was not proven.
        </p>
      </div>

      <Card className="space-y-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Input
            type="datetime-local"
            label="Since"
            aria-label="Filter events since"
            value={sinceLocal}
            onChange={(e) => {
              setSinceLocal(e.target.value)
              setFilters((prev) => ({ ...prev, page: 1 }))
              setSelectedId(null)
            }}
          />
          <Input
            type="datetime-local"
            label="Until"
            aria-label="Filter events until"
            value={untilLocal}
            onChange={(e) => {
              setUntilLocal(e.target.value)
              setFilters((prev) => ({ ...prev, page: 1 }))
              setSelectedId(null)
            }}
          />
          <Select
            label="Actor type"
            aria-label="Filter by actor type"
            options={actorTypeOptions}
            placeholder="Any"
            value={filters.actor_type ?? ''}
            onChange={(e) => updateFilters({ actor_type: e.target.value || undefined })}
          />
          <Input
            label="Actor id"
            aria-label="Filter by actor id"
            value={filters.actor_id ?? ''}
            onChange={(e) => updateFilters({ actor_id: e.target.value.trim() || undefined })}
          />
          <div className="space-y-1.5">
            <label htmlFor="audit-filter-action" className="block text-sm font-medium text-foreground">
              Action
            </label>
            <select
              id="audit-filter-action"
              aria-label="Filter by action"
              multiple
              size={4}
              className="w-full rounded-lg border border-border bg-surface1 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={selectedActions}
              onChange={handleActionChange}
            >
              {actionOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <Select
            label="Resource type"
            aria-label="Filter by resource type"
            options={resourceTypeOptions}
            placeholder="Any"
            value={filters.resource_type ?? ''}
            onChange={(e) => updateFilters({ resource_type: e.target.value || undefined })}
          />
          <Input
            label="Resource id"
            aria-label="Filter by resource id"
            value={filters.resource_id ?? ''}
            onChange={(e) => updateFilters({ resource_id: e.target.value.trim() || undefined })}
          />
          <div className="space-y-1.5">
            <label htmlFor="audit-filter-outcome" className="block text-sm font-medium text-foreground">
              Outcome
            </label>
            <select
              id="audit-filter-outcome"
              aria-label="Filter by outcome"
              multiple
              size={4}
              className="w-full rounded-lg border border-border bg-surface1 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={selectedOutcomes}
              onChange={handleOutcomeChange}
            >
              {outcomeOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner size="lg" />
        </div>
      ) : error ? (
        <EmptyState
          className="[&_h3]:text-destructive"
          title="Failed to load audit history"
          description={apiErrorMessage(error, 'Could not fetch audit events.')}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No audit events" description="Try adjusting your filters." />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Outcome</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((event) => {
                  const isSelected = selectedId === event.id
                  return (
                    <TableRow
                      key={event.id}
                      data-state={isSelected ? 'selected' : undefined}
                      className="cursor-pointer"
                      onClick={() => setSelectedId(event.id)}
                    >
                      <TableCell>
                        <time
                          dateTime={event.occurred_at}
                          title={event.occurred_at}
                          className="whitespace-nowrap text-sm"
                        >
                          {formatDate(event.occurred_at)}
                        </time>
                      </TableCell>
                      <TableCell className="max-w-[12rem] truncate text-sm">{formatActor(event)}</TableCell>
                      <TableCell className="font-mono text-xs">{event.action}</TableCell>
                      <TableCell className="max-w-[14rem] truncate text-sm">{formatResource(event)}</TableCell>
                      <TableCell>
                        <Badge variant={auditOutcomeBadgeVariant(event.outcome)}>
                          {auditOutcomeLabel(event.outcome)}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          {data.pages > 1 && (
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPageChange={(page) => setFilters((prev) => ({ ...prev, page }))}
            />
          )}

          {selectedEvent && (
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-foreground">Event summary</h3>
              {formatAuditSummaryEntries(selectedEvent.summary).length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground">No summary fields.</p>
              ) : (
                <dl className="mt-3 space-y-2">
                  {formatAuditSummaryEntries(selectedEvent.summary).map(({ key, value }) => (
                    <div key={key} className="grid gap-1 sm:grid-cols-[8rem_1fr]">
                      <dt className="text-xs font-medium text-muted-foreground">{key}</dt>
                      <dd className="break-all font-mono text-xs text-foreground">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  )
}

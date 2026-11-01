import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Paperclip, Plus, Robot } from '@phosphor-icons/react'
import {
  useReports,
  useReportSources,
  useCreateReport,
} from '@/hooks/useReports'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/Table'
import { Toggle } from '@/components/ui/Toggle'
import { ReportForm } from '@/components/reports/ReportForm'
import { formatDate } from '@/lib/utils'
import { apiErrorMessage } from '@/lib/apiError'
import type { ReportCreate, ReportFilters, ReportOrigin } from '@/types/report'

const ORIGIN_OPTIONS = [
  { value: '', label: 'All origins' },
  { value: 'provider', label: 'Provider' },
  { value: 'internal', label: 'Internal' },
]

const DEFAULT_FILTERS: ReportFilters = {
  page: 1,
  size: 25,
  q: undefined,
}

export default function ReportsPage() {
  const [filters, setFilters] = useState<ReportFilters>(DEFAULT_FILTERS)
  const [searchParams, setSearchParams] = useSearchParams()
  const { isAdmin } = useAuth()
  const { toast } = useToast()
  const createReport = useCreateReport()

  const { data, isLoading, error } = useReports(filters)
  const { data: sources = [] } = useReportSources()

  const showCreateDialog = isAdmin && searchParams.get('create') === '1'

  useEffect(() => {
    const q = searchParams.get('q')?.trim() || undefined
    setFilters((current) =>
      current.q === q ? current : { ...current, q, page: 1 },
    )
    if (searchParams.get('create') === '1' && !isAdmin) {
      const next = new URLSearchParams(searchParams)
      next.delete('create')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, isAdmin, setSearchParams])

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

  const updateFilters = (partial: Partial<ReportFilters>) => {
    setFilters((f) => ({ ...f, ...partial, page: partial.page ?? 1 }))
  }

  const handleSearchChange = (value: string) => {
    const q = value.trim() || undefined
    updateFilters({ q })
    const params = new URLSearchParams(searchParams)
    if (q) params.set('q', q)
    else params.delete('q')
    setSearchParams(params, { replace: true })
  }

  const handleCreate = (payload: ReportCreate) => {
    createReport.mutate(payload, {
      onSuccess: () => {
        toast('Report created', 'success')
        closeCreateDialog()
      },
      onError: (err) => {
        toast(apiErrorMessage(err, 'Failed to create report'), 'error')
      },
    })
  }

  const sourceOptions = [
    { value: '', label: 'All sources' },
    ...sources.map((name) => ({ value: name, label: name })),
  ]

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:flex-wrap sm:items-end">
          <Input
            label="Search"
            aria-label="Search reports by title or summary"
            value={filters.q ?? ''}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Title or summary…"
            className="min-w-[200px] flex-1"
          />
          <Select
            label="Origin"
            aria-label="Filter by origin"
            options={ORIGIN_OPTIONS}
            value={filters.origin ?? ''}
            onChange={(e) =>
              updateFilters({ origin: (e.target.value || undefined) as ReportOrigin | undefined })
            }
            className="w-full sm:w-40"
          />
          <Select
            label="Source"
            aria-label="Filter by source"
            options={sourceOptions}
            value={filters.source_name ?? ''}
            onChange={(e) => updateFilters({ source_name: e.target.value || undefined })}
            className="w-full sm:w-44"
          />
          <Input
            label="Published from"
            type="date"
            value={filters.published_from ?? ''}
            onChange={(e) => updateFilters({ published_from: e.target.value || undefined })}
            className="w-full sm:w-40"
          />
          <Input
            label="Published to"
            type="date"
            value={filters.published_to ?? ''}
            onChange={(e) => updateFilters({ published_to: e.target.value || undefined })}
            className="w-full sm:w-40"
          />
          <Toggle
            checked={filters.ai_generated === true}
            onChange={(checked) =>
              updateFilters({ ai_generated: checked ? true : undefined })
            }
            label="AI-generated only"
            className="pb-1 sm:pb-2"
          />
        </CardContent>
      </Card>

      {isAdmin && (
        <div className="flex justify-end">
          <Button variant="brand" onClick={openCreateDialog}>
            <Plus size={16} weight="bold" aria-hidden="true" />
            New report
          </Button>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <LoadingSpinner size="lg" />
        </div>
      ) : error ? (
        <EmptyState
          className="[&_h3]:text-destructive"
          title="Failed to load reports"
          description={error instanceof Error ? error.message : 'Unknown error'}
        />
      ) : !data || data.items.length === 0 ? (
        <Card>
          <EmptyState
            title="No reports found"
            description={
              filters.q || filters.origin || filters.source_name
                ? 'Try adjusting your search or filters.'
                : 'Reports from providers and internal sources will appear here.'
            }
          >
            {isAdmin && (
              <Button onClick={openCreateDialog}>
                <Plus size={16} weight="bold" aria-hidden="true" />
                New report
              </Button>
            )}
          </EmptyState>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader className="border-b border-border py-4">
              <CardTitle className="font-mono text-sm tabular-nums">
                {data.total} reports
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Origin</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Published</TableHead>
                    <TableHead className="w-24">Flags</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((report) => (
                    <TableRow key={report.id}>
                      <TableCell>
                        <Link
                          to={`/reports/${report.id}`}
                          className="font-medium text-foreground hover:text-primary"
                        >
                          {report.title}
                        </Link>
                        {report.summary && (
                          <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                            {report.summary}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className="capitalize text-muted-foreground">
                        {report.origin}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {report.source_name ?? '—'}
                      </TableCell>
                      <TableCell className="font-mono text-xs tabular-nums text-muted-foreground">
                        {formatDate(report.published_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {report.is_ai_generated && (
                            <Badge variant="secondary" title="AI-generated">
                              <Robot size={12} aria-hidden="true" />
                              AI
                            </Badge>
                          )}
                          {report.has_attachment && (
                            <Badge variant="outline" title="Has attachment">
                              <Paperclip size={12} aria-hidden="true" />
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {data.pages > 1 && (
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
            />
          )}
        </>
      )}

      <Dialog open={showCreateDialog} onClose={closeCreateDialog} title="New report">
        <ReportForm
          onSubmit={handleCreate}
          onCancel={closeCreateDialog}
          isLoading={createReport.isPending}
        />
      </Dialog>
    </div>
  )
}

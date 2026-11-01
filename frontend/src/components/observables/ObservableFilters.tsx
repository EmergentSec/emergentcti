import { MagnifyingGlass, Export, DownloadSimple, CaretDown } from '@phosphor-icons/react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Slider } from '@/components/ui/Slider'
import { Popover } from '@/components/ui/Popover'
import { useFeeds } from '@/hooks/useFeeds'
import { blocklistUrl, jsonExportUrl } from '@/api/export'
import { typeLabels } from '@/lib/utils'
import type { ObservableFilters as Filters } from '@/types/observable'

const typeOptions = [
  { value: '', label: 'All types' },
  ...Object.entries(typeLabels).map(([value, label]) => ({ value, label })),
]

interface ObservableFiltersProps {
  filters: Filters
  onChange: (filters: Filters) => void
}

export function ObservableFilters({ filters, onChange }: ObservableFiltersProps) {
  const { data: feeds } = useFeeds()
  const update = (partial: Partial<Filters>) => {
    onChange({ ...filters, ...partial, page: 1 })
  }

  const sourceOptions = [
    { value: '', label: 'All sources' },
    { value: 'manual', label: 'Manual only' },
    ...(feeds?.map((f) => ({ value: f.id, label: f.name })) ?? []),
  ]

  const confValue = filters.confidence_min ?? 0
  const exportFilters = { type: filters.type || undefined, confidence_min: confValue > 0 ? confValue : undefined, source: filters.source }

  const exportTrigger = (
    <Button type="button" variant="outline">
      <Export size={14} weight="bold" />
      Export
      <CaretDown size={12} weight="bold" />
    </Button>
  )

  return (
    <Card>
      <CardHeader className="pb-4">
        <CardTitle>Filter observables</CardTitle>
        <CardDescription>Search indicators and narrow results by type, source, or confidence.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
      {/* Row 1: search + type + source */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full sm:min-w-0 sm:flex-1">
          <MagnifyingGlass
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            type="text"
            placeholder="Search by value…"
            value={filters.q ?? ''}
            onChange={(e) => update({ q: e.target.value || undefined })}
            aria-label="Search observables by value"
            className="pl-8"
          />
        </div>

        <div className="w-full sm:w-44">
          <Select
            options={typeOptions}
            value={filters.type ?? ''}
            onChange={(e) => update({ type: (e.target.value as Filters['type']) || undefined })}
          />
        </div>

        <div className="w-full sm:w-48">
          <Select
            options={sourceOptions}
            value={filters.source ?? ''}
            onChange={(e) => update({ source: e.target.value || undefined })}
          />
        </div>
      </div>

      {/* Row 2: min confidence slider + export */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex w-full min-w-0 items-center gap-3 sm:flex-1">
          <span className="shrink-0 text-sm text-muted-foreground">Min conf</span>
          <Slider
            value={confValue}
            min={0}
            max={100}
            step={5}
            onChange={(val) => update({ confidence_min: val > 0 ? val : undefined })}
            className="flex-1"
          />
          <span className="w-8 shrink-0 text-right font-mono text-sm tabular-nums text-foreground">
            {confValue}
          </span>
        </div>

        <Popover trigger={exportTrigger} align="end">
          <div className="py-1 text-sm">
            <p className="px-3 pb-1 pt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Firewall blocklist (plain text)
            </p>
            {(
              [
                { type: 'ip-addr', label: 'IP Addresses' },
                { type: 'domain-name', label: 'Domains' },
                { type: 'url', label: 'URLs' },
              ] as const
            ).map(({ type, label }) => (
              <a
                key={type}
                href={blocklistUrl(type, exportFilters)}
                download
                className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-foreground hover:bg-hover"
              >
                <span>{label}</span>
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <code className="text-xs">{`/blocklist/${type}`}</code>
                  <DownloadSimple size={13} />
                </span>
              </a>
            ))}
            <div className="my-1 border-t border-border" />
            <p className="px-3 pb-1 pt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Full export
            </p>
            <a
              href={jsonExportUrl(exportFilters)}
              download
              className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-foreground hover:bg-hover"
            >
              <span>Full JSON export</span>
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <code className="text-xs">/export/json</code>
                <DownloadSimple size={13} />
              </span>
            </a>
          </div>
        </Popover>
      </div>
      </CardContent>
    </Card>
  )
}

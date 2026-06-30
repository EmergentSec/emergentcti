import { MagnifyingGlass, Export, DownloadSimple, CaretDown } from '@phosphor-icons/react'
import { Card } from '@/components/ui/Card'
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
  const exportFilters = { confidence_min: confValue > 0 ? confValue : undefined, source: filters.source }

  const exportTrigger = (
    <div className="inline-flex h-9 cursor-pointer items-center rounded-md border border-input bg-background text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground select-none">
      <span className="flex items-center gap-1.5 px-3 border-r border-input">
        <Export size={14} weight="bold" />
        Export
      </span>
      <span className="flex items-center px-2">
        <CaretDown size={12} weight="bold" />
      </span>
    </div>
  )

  return (
    <Card className="p-4 space-y-3">
      {/* Row 1: search + type + source */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1">
          <MagnifyingGlass
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            type="text"
            placeholder="Search by value…"
            value={filters.q ?? ''}
            onChange={(e) => update({ q: e.target.value || undefined })}
            className="flex h-9 w-full rounded-md border border-input bg-background py-1 pl-8 pr-3 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div className="w-44">
          <Select
            options={typeOptions}
            value={filters.type ?? ''}
            onChange={(e) => update({ type: (e.target.value as Filters['type']) || undefined })}
          />
        </div>

        <div className="w-48">
          <Select
            options={sourceOptions}
            value={filters.source ?? ''}
            onChange={(e) => update({ source: e.target.value || undefined })}
          />
        </div>
      </div>

      {/* Row 2: min confidence slider + export */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex flex-1 items-center gap-3 min-w-[220px]">
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
                className="flex items-center justify-between gap-3 rounded px-3 py-1.5 text-foreground hover:bg-accent"
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
              className="flex items-center justify-between gap-3 rounded px-3 py-1.5 text-foreground hover:bg-accent"
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
    </Card>
  )
}

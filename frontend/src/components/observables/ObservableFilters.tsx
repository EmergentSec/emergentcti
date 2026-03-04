import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useFeeds } from '@/hooks/useFeeds'
import type { ObservableFilters as Filters } from '@/types/observable'

const typeOptions = [
  { value: '', label: 'All Types' },
  { value: 'ip-addr', label: 'IP Address' },
  { value: 'domain-name', label: 'Domain' },
  { value: 'url', label: 'URL' },
  { value: 'file-hash', label: 'File Hash' },
  { value: 'email-addr', label: 'Email' },
  { value: 'command-line', label: 'Command Line' },
]

const sortOptions = [
  { value: 'last_seen', label: 'Last Seen' },
  { value: 'confidence_score', label: 'Confidence' },
  { value: 'first_seen', label: 'First Seen' },
  { value: 'value', label: 'Value' },
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
    { value: '', label: 'All Sources' },
    { value: 'manual', label: 'Manual Only' },
    ...(feeds?.map((f) => ({ value: f.id, label: f.name })) ?? []),
  ]

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="min-w-[200px] flex-1">
        <Input
          placeholder="Search observables..."
          value={filters.q || ''}
          onChange={(e) => update({ q: e.target.value || undefined })}
        />
      </div>

      <div className="w-40">
        <Select
          options={typeOptions}
          value={filters.type || ''}
          onChange={(e) => update({ type: (e.target.value as Filters['type']) || undefined })}
        />
      </div>

      <div className="w-48">
        <Select
          options={sourceOptions}
          value={filters.source || ''}
          onChange={(e) => update({ source: e.target.value || undefined })}
        />
      </div>

      <div className="w-36">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">Min Confidence</label>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={filters.confidence_min ?? 0}
              onChange={(e) => {
                const val = parseInt(e.target.value)
                update({ confidence_min: val > 0 ? val : undefined })
              }}
              className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-muted accent-primary"
            />
            <span className="min-w-[2rem] text-right text-xs tabular-nums text-muted-foreground">
              {filters.confidence_min ?? 0}
            </span>
          </div>
        </div>
      </div>

      <div className="w-36">
        <Select
          options={sortOptions}
          value={filters.sort || 'last_seen'}
          onChange={(e) => update({ sort: e.target.value })}
        />
      </div>

      <div className="w-24">
        <Select
          options={[
            { value: 'desc', label: 'Desc' },
            { value: 'asc', label: 'Asc' },
          ]}
          value={filters.order || 'desc'}
          onChange={(e) => update({ order: e.target.value as 'asc' | 'desc' })}
        />
      </div>
    </div>
  )
}

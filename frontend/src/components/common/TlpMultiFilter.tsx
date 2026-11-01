import { useMemo } from 'react'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { X } from '@phosphor-icons/react'
import { TLP_FILTER_OPTIONS } from '@/lib/tlp'
import type { TlpFilterValue } from '@/types/tlp'

interface TlpMultiFilterProps {
  selected: TlpFilterValue[]
  onChange: (values: TlpFilterValue[]) => void
  label?: string
  className?: string
}

export function TlpMultiFilter({
  selected,
  onChange,
  label = 'TLP',
  className,
}: TlpMultiFilterProps) {
  const options = useMemo(
    () => TLP_FILTER_OPTIONS.filter((o) => o.value !== ''),
    [],
  )

  const addValue = (raw: string) => {
    if (!raw) return
    const value = raw as TlpFilterValue
    if (selected.includes(value)) return
    onChange([...selected, value])
  }

  const removeValue = (value: TlpFilterValue) => {
    onChange(selected.filter((v) => v !== value))
  }

  const labelFor = (value: TlpFilterValue) =>
    TLP_FILTER_OPTIONS.find((o) => o.value === value)?.label ?? value

  return (
    <div className={className}>
      {label && (
        <span className="mb-1 block text-sm font-medium text-foreground">{label}</span>
      )}
      <Select
        aria-label={label}
        options={[{ value: '', label: 'Add TLP filter…' }, ...options]}
        value=""
        onChange={(e) => addValue(e.target.value)}
        className="h-9 w-full text-xs sm:w-48"
      />
      {selected.length > 0 && (
        <span className="mt-2 inline-flex flex-wrap gap-1">
          {selected.map((value) => (
            <Badge key={value} variant="outline" className="gap-1 pr-1">
              {labelFor(value)}
              <button
                type="button"
                className="rounded-full p-0.5 hover:bg-hover"
                aria-label={`Remove TLP filter ${labelFor(value)}`}
                onClick={() => removeValue(value)}
              >
                <X size={12} weight="bold" />
              </button>
            </Badge>
          ))}
        </span>
      )}
    </div>
  )
}

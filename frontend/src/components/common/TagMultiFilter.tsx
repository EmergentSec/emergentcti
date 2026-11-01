import { useMemo } from 'react'
import { useTags } from '@/hooks/useTags'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { X } from '@phosphor-icons/react'

interface TagMultiFilterProps {
  selected: string[]
  onChange: (tags: string[]) => void
  label?: string
  className?: string
}

export function TagMultiFilter({
  selected,
  onChange,
  label = 'Tag',
  className,
}: TagMultiFilterProps) {
  const { data: allTags = [] } = useTags()

  const options = useMemo(() => {
    const names = new Set<string>()
    for (const t of allTags) names.add(t.name)
    for (const s of selected) names.add(s)
    return [
      { value: '', label: 'Add tag filter…' },
      ...[...names].sort().map((name) => ({ value: name, label: name })),
    ]
  }, [allTags, selected])

  const addTag = (name: string) => {
    if (!name || selected.includes(name)) return
    onChange([...selected, name])
  }

  const removeTag = (name: string) => {
    onChange(selected.filter((t) => t !== name))
  }

  return (
    <div className={className}>
      {label && (
        <span className="mb-1 block text-sm font-medium text-foreground">{label}</span>
      )}
      <Select
        aria-label={label}
        options={options}
        value=""
        onChange={(e) => addTag(e.target.value)}
        className="h-9 w-full text-xs sm:w-48"
      />
      {selected.length > 0 && (
        <span className="mt-2 inline-flex flex-wrap gap-1">
          {selected.map((tag) => (
            <Badge key={tag} variant="outline" className="gap-1 pr-1">
              {tag}
              <button
                type="button"
                className="rounded-full p-0.5 hover:bg-hover"
                aria-label={`Remove tag filter ${tag}`}
                onClick={() => removeTag(tag)}
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

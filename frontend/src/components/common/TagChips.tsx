import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

interface TagChipsProps {
  tags: string[]
  className?: string
  emptyLabel?: string
}

export function TagChips({ tags, className, emptyLabel }: TagChipsProps) {
  if (tags.length === 0) {
    if (!emptyLabel) return null
    return <span className={cn('text-sm text-muted-foreground', className)}>{emptyLabel}</span>
  }

  return (
    <span className={cn('inline-flex flex-wrap gap-1', className)}>
      {tags.map((tag) => (
        <Badge key={tag} variant="secondary" title={`Tag: ${tag}`}>
          {tag}
        </Badge>
      ))}
    </span>
  )
}

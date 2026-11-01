import { useId, useState } from 'react'
import { X } from '@phosphor-icons/react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { normalizeTagName, validateTagName } from '@/lib/tagNormalization'
import { cn } from '@/lib/utils'

interface TagEditorProps {
  tags: string[]
  onChange: (tags: string[]) => void
  onSave: () => void
  isSaving?: boolean
  className?: string
  showSaveButton?: boolean
}

export function TagEditor({
  tags,
  onChange,
  onSave,
  isSaving,
  className,
  showSaveButton = true,
}: TagEditorProps) {
  const draftInputId = useId()
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  const addTag = () => {
    const normalized = normalizeTagName(draft)
    const validation = validateTagName(normalized)
    if (validation) {
      setError(validation)
      return
    }
    if (tags.includes(normalized)) {
      setError('Tag is already in the list')
      return
    }
    setError(null)
    onChange([...tags, normalized].sort())
    setDraft('')
  }

  const removeTag = (name: string) => {
    onChange(tags.filter((t) => t !== name))
  }

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap gap-1">
        {tags.length === 0 ? (
          <span className="text-sm text-muted-foreground">No tags assigned</span>
        ) : (
          tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1 pr-1">
              {tag}
              <button
                type="button"
                className="rounded-full p-0.5 hover:bg-surface3"
                aria-label={`Remove tag ${tag}`}
                onClick={() => removeTag(tag)}
              >
                <X size={12} weight="bold" />
              </button>
            </Badge>
          ))
        )}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="sm:flex-1">
          <Input
            id={draftInputId}
            label="Add tag"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="e.g. ransomware"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addTag()
              }
            }}
            error={error ?? undefined}
            disabled={isSaving}
          />
        </div>
        <Button type="button" variant="outline" size="sm" onClick={addTag} disabled={isSaving}>
          Add
        </Button>
        {showSaveButton && (
          <Button type="button" size="sm" onClick={onSave} disabled={isSaving}>
            {isSaving ? 'Saving…' : 'Save tags'}
          </Button>
        )}
      </div>
    </div>
  )
}

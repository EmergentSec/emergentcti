import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { TagEditor } from '@/components/common/TagEditor'
import { TlpDowngradeReasonDialog } from '@/components/common/TlpDowngradeReasonDialog'
import type { ContentFormat, ReportCreate, ReportDetail, ReportOrigin } from '@/types/report'
import {
  TLP_SELECT_OPTIONS,
  formatTlpSelectValue,
  needsTlpChangeReason,
  parseTlpSelectValue,
} from '@/lib/tlp'
import { cn } from '@/lib/utils'

interface ReportFormProps {
  initial?: ReportDetail | null
  onSubmit: (data: ReportCreate) => void
  onCancel: () => void
  isLoading?: boolean
  isAdmin?: boolean
}

const originOptions = [
  { value: 'provider', label: 'External provider' },
  { value: 'internal', label: 'Internal' },
]

const formatOptions = [
  { value: 'markdown', label: 'Markdown' },
  { value: 'text', label: 'Plain text' },
]

function toDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fromDatetimeLocal(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const d = new Date(trimmed)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

export function ReportForm({ initial, onSubmit, onCancel, isLoading, isAdmin }: ReportFormProps) {
  const [title, setTitle] = useState('')
  const [origin, setOrigin] = useState<ReportOrigin>('provider')
  const [sourceName, setSourceName] = useState('')
  const [publishedAt, setPublishedAt] = useState('')
  const [summary, setSummary] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [content, setContent] = useState('')
  const [contentFormat, setContentFormat] = useState<ContentFormat>('markdown')
  const [isAiGenerated, setIsAiGenerated] = useState(false)
  const [aiProvider, setAiProvider] = useState('')
  const [aiModel, setAiModel] = useState('')
  const [aiGeneratedAt, setAiGeneratedAt] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [tlpValue, setTlpValue] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [showDowngradeDialog, setShowDowngradeDialog] = useState(false)
  const [pendingPayload, setPendingPayload] = useState<ReportCreate | null>(null)

  useEffect(() => {
    if (!initial) return
    setTitle(initial.title)
    setOrigin(initial.origin)
    setSourceName(initial.source_name ?? '')
    setPublishedAt(toDatetimeLocal(initial.published_at))
    setSummary(initial.summary ?? '')
    setSourceUrl(initial.source_url ?? '')
    setContent(initial.content ?? '')
    setContentFormat(initial.content_format)
    setIsAiGenerated(initial.is_ai_generated)
    setAiProvider(initial.ai_provider ?? '')
    setAiModel(initial.ai_model ?? '')
    setAiGeneratedAt(toDatetimeLocal(initial.ai_generated_at))
    setTlpValue(formatTlpSelectValue(initial.tlp))
    setTags(initial.tags ?? [])
  }, [initial])

  const validate = (): boolean => {
    const next: Record<string, string> = {}
    if (!title.trim()) next.title = 'Title is required'
    else if (title.trim().length > 500) next.title = 'Title must be 500 characters or fewer'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const buildPayload = (): ReportCreate => {
    const payload: ReportCreate = {
      title: title.trim(),
      origin,
      source_name: sourceName.trim() || null,
      published_at: fromDatetimeLocal(publishedAt),
      summary: summary.trim() || null,
      source_url: sourceUrl.trim() || null,
      content: content.trim() || null,
      content_format: contentFormat,
      is_ai_generated: isAiGenerated,
      tlp: parseTlpSelectValue(tlpValue),
    }

    if (isAiGenerated) {
      payload.ai_provider = aiProvider.trim() || null
      payload.ai_model = aiModel.trim() || null
      payload.ai_generated_at = fromDatetimeLocal(aiGeneratedAt)
    }

    if (isAdmin) {
      payload.tags = tags
    }

    return payload
  }

  const submitPayload = (payload: ReportCreate, reason?: string) => {
    if (reason) payload.tlp_change_reason = reason
    onSubmit(payload)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    const payload = buildPayload()
    if (initial && needsTlpChangeReason(initial.tlp, payload.tlp ?? null)) {
      setPendingPayload(payload)
      setShowDowngradeDialog(true)
      return
    }
    submitPayload(payload)
  }

  const handleDowngradeConfirm = (reason: string) => {
    if (pendingPayload) submitPayload(pendingPayload, reason)
    setPendingPayload(null)
    setShowDowngradeDialog(false)
  }

  return (
    <>
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        error={errors.title}
        maxLength={500}
        required
      />

      <Select
        label="Origin"
        options={originOptions}
        value={origin}
        onChange={(e) => setOrigin(e.target.value as ReportOrigin)}
      />

      <Input
        label={origin === 'provider' ? 'Provider name' : 'Author'}
        value={sourceName}
        onChange={(e) => setSourceName(e.target.value)}
        placeholder={origin === 'provider' ? 'e.g. Mandiant' : 'e.g. analyst@example.com'}
      />

      <Input
        label="Published date"
        type="datetime-local"
        value={publishedAt}
        onChange={(e) => setPublishedAt(e.target.value)}
      />

      <Input
        label="Summary"
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder="Optional short summary"
      />

      <Input
        label="Source URL"
        value={sourceUrl}
        onChange={(e) => setSourceUrl(e.target.value)}
        placeholder="https://…"
      />

      <Select
        label="TLP marking"
        options={TLP_SELECT_OPTIONS}
        value={tlpValue}
        onChange={(e) => setTlpValue(e.target.value)}
      />

      {isAdmin && (
        <div className="space-y-2">
          <span className="text-sm font-medium text-foreground">Tags</span>
          <TagEditor
            tags={tags}
            onChange={setTags}
            onSave={() => {}}
            showSaveButton={false}
          />
          <p className="text-xs text-muted-foreground">
            Tags are saved with the report when you submit this form.
          </p>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-medium text-foreground">Content format</span>
          <Select
            aria-label="Content format"
            options={formatOptions}
            value={contentFormat}
            onChange={(e) => setContentFormat(e.target.value as ContentFormat)}
            className="h-9 w-40 text-xs"
          />
        </div>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={8}
          placeholder={contentFormat === 'markdown' ? 'Markdown content…' : 'Plain text content…'}
          className={cn(
            'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground',
            'placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
          )}
        />
      </div>

      <Toggle
        checked={isAiGenerated}
        onChange={setIsAiGenerated}
        label="AI-generated report"
      />

      {isAiGenerated && (
        <div className="space-y-3 rounded-lg border border-border bg-surface2 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">AI provenance</p>
          <Input
            label="AI provider"
            value={aiProvider}
            onChange={(e) => setAiProvider(e.target.value)}
            placeholder="Leave blank if unknown"
          />
          <Input
            label="AI model"
            value={aiModel}
            onChange={(e) => setAiModel(e.target.value)}
            placeholder="Leave blank if unknown"
          />
          <Input
            label="Generated at"
            type="datetime-local"
            value={aiGeneratedAt}
            onChange={(e) => setAiGeneratedAt(e.target.value)}
          />
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving…' : initial ? 'Save changes' : 'Create report'}
        </Button>
      </div>
    </form>
      <TlpDowngradeReasonDialog
        open={showDowngradeDialog}
        onClose={() => {
          setShowDowngradeDialog(false)
          setPendingPayload(null)
        }}
        isLoading={isLoading}
        onConfirm={handleDowngradeConfirm}
      />
    </>
  )
}

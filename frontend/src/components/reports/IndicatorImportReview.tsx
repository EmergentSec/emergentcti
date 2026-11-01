import { useEffect, useMemo, useRef, useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/Table'
import { useImportReportIndicators } from '@/hooks/useReports'
import { useToast } from '@/contexts/ToastContext'
import { importValidationErrorDetail } from '@/lib/apiError'
import {
  CONFIDENCE_HELP_TEXT,
  EXPORT_ELIGIBILITY_NOTICE,
  PDF_EXTRACTION_MESSAGE,
  candidateKey,
  formatExtractionWarning,
  isDefaultSelectedCandidate,
  isSelectableCandidate,
} from '@/lib/extractionWarnings'
import { cn, typeLabels } from '@/lib/utils'
import type { ExtractionCandidate, ExtractionPreview, ExtractionSource } from '@/types/reportIocExtraction'

export interface IndicatorImportReviewProps {
  open: boolean
  onClose: () => void
  preview: ExtractionPreview
}

function sourceLabel(source: ExtractionSource): string {
  if (source.kind === 'content') return 'Report content'
  const name = source.filename ?? 'Attachment'
  return source.content_type ? `${name} (${source.content_type})` : name
}

function sourceStatusText(source: ExtractionSource): string {
  if (source.status === 'extracted') return 'Text extracted'
  if (source.status === 'empty') return 'Empty'
  if (source.reason === 'pdf_text_extraction_unavailable') return 'Unsupported (PDF)'
  if (source.reason) return source.reason.replace(/_/g, ' ')
  return 'Unsupported'
}

function parseConfidenceInput(raw: string): { valid: boolean; value: number } {
  const trimmed = raw.trim()
  if (trimmed === '') return { valid: false, value: NaN }
  const n = Number(trimmed)
  if (!Number.isInteger(n) || n < 0 || n > 100) return { valid: false, value: n }
  return { valid: true, value: n }
}

function statusBadgeVariant(status: ExtractionCandidate['status']): 'default' | 'secondary' | 'destructive' {
  if (status === 'new') return 'default'
  if (status === 'existing') return 'secondary'
  return 'destructive'
}

function PlainValue({ text, className }: { text: string; className?: string }) {
  return (
    <span className={className} title={text.length > 48 ? text : undefined}>
      {text}
    </span>
  )
}

function buildInitialSelection(candidates: ExtractionCandidate[]): Set<string> {
  const selected = new Set<string>()
  for (const c of candidates) {
    if (isDefaultSelectedCandidate(c)) {
      selected.add(candidateKey(c.type, c.value))
    }
  }
  return selected
}

export function IndicatorImportReview({ open, onClose, preview }: IndicatorImportReviewProps) {
  const { toast } = useToast()
  const importIndicators = useImportReportIndicators()
  const submittingRef = useRef(false)
  const [selected, setSelected] = useState<Set<string>>(() => buildInitialSelection(preview.candidates))
  const [confidence, setConfidence] = useState('50')
  const [importDetail, setImportDetail] = useState<string | null>(null)
  const [highlightedKeys, setHighlightedKeys] = useState<Set<string>>(() => new Set())

  const clearImportFeedback = () => {
    setImportDetail(null)
    setHighlightedKeys(new Set())
  }

  useEffect(() => {
    if (open) {
      setSelected(buildInitialSelection(preview.candidates))
      setConfidence('50')
      clearImportFeedback()
    }
  }, [open, preview])

  const confidenceParsed = useMemo(() => parseConfidenceInput(confidence), [confidence])
  const confidenceError = confidenceParsed.valid ? undefined : 'Input error'

  const selectableKeys = useMemo(
    () =>
      preview.candidates.filter(isSelectableCandidate).map((c) => candidateKey(c.type, c.value)),
    [preview.candidates],
  )

  const selectedCount = useMemo(() => {
    let n = 0
    for (const key of selectableKeys) {
      if (selected.has(key)) n += 1
    }
    return n
  }, [selectableKeys, selected])

  const toggleRow = (candidate: ExtractionCandidate) => {
    if (!isSelectableCandidate(candidate)) return
    clearImportFeedback()
    const key = candidateKey(candidate.type, candidate.value)
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const selectAll = () => {
    clearImportFeedback()
    setSelected(new Set(selectableKeys))
  }

  const selectNone = () => {
    clearImportFeedback()
    setSelected(new Set())
  }

  const handleImport = () => {
    if (submittingRef.current || !confidenceParsed.valid) return
    submittingRef.current = true
    clearImportFeedback()

    const items = preview.candidates
      .filter((c) => selected.has(candidateKey(c.type, c.value)))
      .map((c) => ({ type: c.type, value: c.value }))

    importIndicators.mutate(
      { reportId: preview.report_id, payload: { confidence: confidenceParsed.value, items } },
      {
        onSuccess: (result) => {
          toast(
            `Import complete: ${result.created} created, ${result.attributed_existing} attributed, ${result.already_attributed} already linked`,
            'success',
          )
          onClose()
        },
        onError: (err) => {
          const parsed = importValidationErrorDetail(err)
          if (parsed) {
            setImportDetail(parsed.messages.join('\n'))
            setHighlightedKeys(
              new Set(parsed.highlightedItems.map((item) => candidateKey(item.type, item.value))),
            )
          } else {
            setImportDetail('Import failed')
          }
        },
        onSettled: () => {
          submittingRef.current = false
        },
      },
    )
  }

  const showPdfNotice = preview.sources.some(
    (s) => s.status === 'unsupported' && s.reason === 'pdf_text_extraction_unavailable',
  )

  const importPending = importIndicators.isPending
  const handleDialogClose = importPending ? () => {} : onClose

  return (
    <Dialog
      open={open}
      onClose={handleDialogClose}
      title="Import indicators from report"
      className="max-h-[90vh] w-full max-w-5xl overflow-hidden"
    >
      <div className="flex max-h-[calc(90vh-4rem)] flex-col gap-4 overflow-hidden">
        <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sources</p>
          <ul className="space-y-1.5">
            {preview.sources.map((source, i) => (
              <li key={`${source.kind}-${source.filename ?? i}`} className="flex flex-wrap gap-x-2 gap-y-1">
                <span className="font-medium">{sourceLabel(source)}</span>
                <span className="text-muted-foreground">—</span>
                <span className="text-muted-foreground">{sourceStatusText(source)}</span>
              </li>
            ))}
          </ul>
          {showPdfNotice && (
            <p className="mt-2 rounded-lg border border-warning bg-warning-soft px-3 py-2 text-sm text-warning-ink">
              {PDF_EXTRACTION_MESSAGE}
            </p>
          )}
          {preview.truncated && (
            <p className="text-xs text-muted-foreground">
              Results were truncated (document size or candidate limit).
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={selectAll}>
            Select all
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={selectNone}>
            Select none
          </Button>
          <span className="text-xs text-muted-foreground">
            {selectedCount} of {selectableKeys.length} selectable
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <span className="sr-only">Select</span>
                </TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Original</TableHead>
                <TableHead>Context</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Flags</TableHead>
                <TableHead>Warnings</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {preview.candidates.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">
                    No candidates found in the report text.
                  </TableCell>
                </TableRow>
              ) : (
                preview.candidates.map((candidate) => {
                  const key = candidateKey(candidate.type, candidate.value)
                  const selectable = isSelectableCandidate(candidate)
                  const checked = selectable && selected.has(key)
                  const showOriginal = candidate.original !== candidate.value
                  const rowHighlighted = highlightedKeys.has(key)

                  return (
                    <TableRow
                      key={key}
                      data-testid={`candidate-row-${key}`}
                      className={cn(rowHighlighted && 'bg-destructive/10 ring-1 ring-inset ring-destructive/40')}
                    >
                      <TableCell>
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                          checked={checked}
                          disabled={!selectable}
                          aria-label={`Select ${candidate.type} ${candidate.value}`}
                          onChange={() => toggleRow(candidate)}
                        />
                      </TableCell>
                      <TableCell>
                        <span className="text-xs">{typeLabels[candidate.type] ?? candidate.type}</span>
                      </TableCell>
                      <TableCell className="max-w-[12rem] font-mono text-xs break-all">
                        <PlainValue text={candidate.value} />
                      </TableCell>
                      <TableCell className="max-w-[10rem] font-mono text-xs break-all text-muted-foreground">
                        {showOriginal ? <PlainValue text={candidate.original} /> : '—'}
                      </TableCell>
                      <TableCell className="max-w-[14rem] text-xs text-muted-foreground break-all">
                        <PlainValue text={candidate.context} />
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusBadgeVariant(candidate.status)} className="capitalize">
                          {candidate.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="flex flex-col gap-0.5">
                          {candidate.already_attributed && (
                            <span className="text-muted-foreground">Already linked</span>
                          )}
                          {candidate.defanged && <span className="text-muted-foreground">Defanged</span>}
                          {candidate.allowlisted && (
                            <span className="text-muted-foreground" title={candidate.allowlist_matches.join(', ')}>
                              Allowlisted
                              {candidate.allowlist_matches.length > 0
                                ? `: ${candidate.allowlist_matches.join(', ')}`
                                : ''}
                            </span>
                          )}
                          {!candidate.already_attributed &&
                            !candidate.defanged &&
                            !candidate.allowlisted &&
                            '—'}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-[12rem] text-xs text-muted-foreground">
                        {candidate.warnings.length === 0
                          ? '—'
                          : candidate.warnings.map((w) => formatExtractionWarning(w)).join('; ')}
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Input
              label="Confidence for new observables"
              type="number"
              min={0}
              max={100}
              value={confidence}
              error={confidenceError}
              onChange={(e) => setConfidence(e.target.value)}
              aria-describedby="import-confidence-help"
            />
            <p id="import-confidence-help" className="text-xs text-muted-foreground">
              {CONFIDENCE_HELP_TEXT}
            </p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{EXPORT_ELIGIBILITY_NOTICE}</p>

        {importDetail && (
          <p className="whitespace-pre-line text-sm text-destructive" role="alert">
            {importDetail}
          </p>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-3">
          <Button type="button" variant="outline" disabled={importPending} onClick={handleDialogClose}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="brand"
            disabled={selectedCount === 0 || importPending || !confidenceParsed.valid}
            onClick={handleImport}
          >
            {importPending
              ? 'Importing…'
              : `Import ${selectedCount} indicator${selectedCount === 1 ? '' : 's'}`}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

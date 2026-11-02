import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import type { OutboundPreview } from '@/types/ai'

export interface OutboundPreviewDialogProps {
  open: boolean
  preview: OutboundPreview | null
  onClose: () => void
  onConfirm: () => void
  confirmLabel?: string
  confirmDisabled?: boolean
  confirmDisabledReason?: string | null
}

function excludedLabel(reason: string | null): string {
  switch (reason) {
    case 'tlp_restricted':
      return 'TLP restricted'
    case 'not_found':
      return 'Not found'
    case 'not_visible':
      return 'Not visible'
    default:
      return reason ?? 'Excluded'
  }
}

export function OutboundPreviewDialog({
  open,
  preview,
  onClose,
  onConfirm,
  confirmLabel = 'Send to provider',
  confirmDisabled = false,
  confirmDisabledReason = null,
}: OutboundPreviewDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title="Review outbound content">
      {!preview ? (
        <p className="text-sm text-muted-foreground">No preview loaded.</p>
      ) : (
        <div className="space-y-4 text-sm">
          <p className="text-muted-foreground">{preview.destination_note}</p>
          <p>
            <span className="text-muted-foreground">Model:</span>{' '}
            <code className="font-mono text-xs">{preview.model}</code>
          </p>
          <ul className="space-y-2">
            {preview.items.map((item) => (
              <li key={`${item.type}-${item.id}`} className="rounded-lg border border-border px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.label}</span>
                  {item.included ? (
                    <Badge variant="success">Included</Badge>
                  ) : (
                    <Badge variant="secondary">{excludedLabel(item.excluded_reason)}</Badge>
                  )}
                  {item.redactions > 0 && (
                    <span className="text-xs text-muted-foreground">{item.redactions} redaction(s)</span>
                  )}
                </div>
                {item.tlp && <p className="text-xs text-muted-foreground">TLP: {item.tlp}</p>}
              </li>
            ))}
          </ul>
          <div>
            <p className="mb-1 font-medium text-foreground">Exact content that would be sent</p>
            <pre className="max-h-48 overflow-auto rounded-lg border border-border bg-surface2 p-3 font-mono text-xs whitespace-pre-wrap">
              {preview.content}
            </pre>
          </div>
          <div className="flex flex-col items-end gap-2 sm:flex-row sm:justify-end">
            {confirmDisabled && confirmDisabledReason && (
              <p className="mr-auto text-xs text-muted-foreground">{confirmDisabledReason}</p>
            )}
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="button" onClick={onConfirm} disabled={confirmDisabled} title={confirmDisabledReason ?? undefined}>
              {confirmLabel}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  )
}

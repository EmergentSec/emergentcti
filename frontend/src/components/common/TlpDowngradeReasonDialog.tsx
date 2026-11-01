import { useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { REASON_MAX_LENGTH } from '@/lib/policyValidation'

interface TlpDowngradeReasonDialogProps {
  open: boolean
  onClose: () => void
  onConfirm: (reason: string) => void
  isLoading?: boolean
}

export function TlpDowngradeReasonDialog({
  open,
  onClose,
  onConfirm,
  isLoading,
}: TlpDowngradeReasonDialogProps) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleClose = () => {
    setReason('')
    setError(null)
    onClose()
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = reason.trim()
    if (!trimmed) {
      setError('Reason is required when loosening a TLP marking')
      return
    }
    if (trimmed.length > REASON_MAX_LENGTH) {
      setError(`Reason must be ${REASON_MAX_LENGTH} characters or fewer`)
      return
    }
    setError(null)
    setReason('')
    onConfirm(trimmed)
  }

  return (
    <Dialog open={open} onClose={handleClose} title="Reason for TLP change">
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Loosening a TLP marking (or clearing it to Unspecified) requires a short reason. It is
          recorded in the server log.
        </p>
        <Input
          id="tlp-change-reason"
          label="Reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={REASON_MAX_LENGTH}
          autoFocus
          error={error ?? undefined}
          disabled={isLoading}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" disabled={isLoading}>
            {isLoading ? 'Saving…' : 'Continue'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

import { useState } from 'react'
import { useAllowlist, useCreateAllowlistEntry, useDeleteAllowlistEntry } from '@/hooks/useAllowlist'
import { useConfig } from '@/hooks/useConfig'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { apiErrorMessage, apiErrorStatus } from '@/lib/apiError'
import {
  REASON_MAX_LENGTH,
  validateAllowlistEntry,
  type AllowlistFormErrors,
} from '@/lib/policyValidation'
import { formatRelativeTime, typeLabels } from '@/lib/utils'
import type { AllowlistEntry, AllowlistKind } from '@/types/allowlist'
import type { ObservableType } from '@/types/observable'

const KIND_LABELS: Record<AllowlistKind, string> = {
  exact: 'Exact value',
  cidr: 'CIDR range',
  domain_suffix: 'Domain suffix',
}

const KIND_OPTIONS = (Object.keys(KIND_LABELS) as AllowlistKind[]).map((kind) => ({
  value: kind,
  label: KIND_LABELS[kind],
}))

const KIND_HINTS: Record<AllowlistKind, string> = {
  exact: 'Matches this value for the chosen type. IPs and domains are normalized; other types match literally, including case and whitespace.',
  cidr: 'Matches every IPv4 or IPv6 address inside the range.',
  domain_suffix:
    'Matches the domain itself and all of its subdomains. It does not match URLs or email addresses on that domain.',
}

const KIND_PLACEHOLDERS: Record<AllowlistKind, string> = {
  exact: 'e.g., 8.8.8.8',
  cidr: 'e.g., 10.0.0.0/8',
  domain_suffix: 'e.g., example.com',
}

// CIDR and domain-suffix entries apply to a single fixed observable type.
const FIXED_TYPE: Partial<Record<AllowlistKind, ObservableType>> = {
  cidr: 'ip-addr',
  domain_suffix: 'domain-name',
}

const TYPE_OPTIONS = Object.entries(typeLabels).map(([value, label]) => ({ value, label }))

function retentionSentence(days: number | undefined): string {
  if (days === undefined) {
    return 'A daily job permanently deletes observables that have not been seen within the retention period.'
  }
  if (days === 0) {
    return 'Retention is currently disabled on this instance, so no observables are being deleted.'
  }
  return `A daily job permanently deletes observables not seen for more than ${days} days.`
}

export function AllowlistManager() {
  const { isAdmin } = useAuth()
  const { toast } = useToast()

  const { data: entries, isLoading, error } = useAllowlist()
  const { data: config } = useConfig()
  const createEntry = useCreateAllowlistEntry()
  const deleteEntry = useDeleteAllowlistEntry()

  // Create dialog state
  const [showCreate, setShowCreate] = useState(false)
  const [kind, setKind] = useState<AllowlistKind>('exact')
  const [observableType, setObservableType] = useState<ObservableType | ''>('')
  const [value, setValue] = useState('')
  const [reason, setReason] = useState('')
  const [formErrors, setFormErrors] = useState<AllowlistFormErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<AllowlistEntry | null>(null)

  const closeCreateDialog = () => {
    setShowCreate(false)
    setKind('exact')
    setObservableType('')
    setValue('')
    setReason('')
    setFormErrors({})
    setSubmitError(null)
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError(null)
    const errors = validateAllowlistEntry({ kind, value, observableType, reason })
    setFormErrors(errors)
    if (Object.keys(errors).length > 0) return

    createEntry.mutate(
      {
        kind,
        value: kind === 'exact' && observableType !== 'ip-addr' && observableType !== 'domain-name'
          ? value
          : value.trim(),
        observable_type: FIXED_TYPE[kind] ?? (observableType || undefined),
        reason: reason.trim(),
      },
      {
        onSuccess: () => {
          toast('Allowlist entry added', 'success')
          closeCreateDialog()
        },
        onError: (err) => {
          const message =
            apiErrorStatus(err) === 409
              ? 'This entry is already on the allowlist.'
              : apiErrorMessage(err, 'Failed to add allowlist entry')
          setSubmitError(message)
          toast(message, 'error')
        },
      },
    )
  }

  const handleDelete = () => {
    if (!deleteTarget) return
    deleteEntry.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast(`${deleteTarget.value} removed from the allowlist`, 'success')
        setDeleteTarget(null)
      },
      onError: (err) => {
        toast(apiErrorMessage(err, 'Failed to remove allowlist entry'), 'error')
        setDeleteTarget(null)
      },
    })
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Allowlist</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Keep known-good values out of every export without deleting them
          </p>
        </div>
        {isAdmin && (
          <Button variant="brand" onClick={() => setShowCreate(true)}>
            Add entry
          </Button>
        )}
      </div>

      {/* Policy explanation: reversible allowlisting vs irreversible retention */}
      <Card className="grid gap-4 p-5 md:grid-cols-2">
        <section aria-labelledby="allowlist-reversible-heading">
          <h3 id="allowlist-reversible-heading" className="text-sm font-semibold text-foreground">
            Allowlisting is reversible
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Matching observables and their sources stay in the database. They are only left out of
            exports: text, JSON, blocklists and saved export profiles. Removing an entry puts its
            matches back into exports immediately — but only for observables that retention has
            not already deleted.
          </p>
        </section>
        <section aria-labelledby="allowlist-retention-heading">
          <h3 id="allowlist-retention-heading" className="text-sm font-semibold text-foreground">
            Retention deletion is irreversible
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {retentionSentence(config?.observable_retention_days)} This applies to allowlisted and
            manually added observables too: allowlisting does not protect an observable from
            retention, and deleted observables cannot be restored. Retention is configured via
            environment.
          </p>
        </section>
      </Card>

      {!isAdmin && (
        <p className="text-sm text-muted-foreground">
          Only administrators can add or remove allowlist entries.
        </p>
      )}

      {/* Entries */}
      {isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : error ? (
        <p role="alert" className="text-sm text-destructive-foreground">
          Failed to load the allowlist
        </p>
      ) : !entries || entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No allowlist entries. Every observable is eligible for export.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>KIND</TableHead>
              <TableHead>VALUE</TableHead>
              <TableHead>APPLIES TO</TableHead>
              <TableHead>REASON</TableHead>
              <TableHead>ADDED</TableHead>
              {isAdmin && <TableHead className="w-20" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell>
                  <Badge variant="secondary" className="whitespace-nowrap">
                    {KIND_LABELS[entry.kind] ?? entry.kind}
                  </Badge>
                </TableCell>
                <TableCell className="break-all font-mono text-sm text-foreground">
                  {entry.value}
                </TableCell>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {typeLabels[entry.observable_type] ?? entry.observable_type}
                </TableCell>
                <TableCell className="text-muted-foreground">{entry.reason}</TableCell>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {formatRelativeTime(entry.created_at)}
                </TableCell>
                {isAdmin && (
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove ${entry.value} from the allowlist`}
                      onClick={() => setDeleteTarget(entry)}
                      className="text-destructive hover:text-destructive"
                    >
                      Remove
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Create dialog */}
      <Dialog open={showCreate} onClose={closeCreateDialog} title="Add allowlist entry">
        <form onSubmit={handleCreate} noValidate className="space-y-4">
          <div className="space-y-1.5">
            <Select
              id="allowlist-kind"
              label="Match kind"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value as AllowlistKind)
                setFormErrors({})
              }}
              options={KIND_OPTIONS}
              aria-describedby="allowlist-kind-hint"
            />
            <p id="allowlist-kind-hint" className="text-xs text-muted-foreground">
              {KIND_HINTS[kind]}
            </p>
          </div>
          <div className="space-y-1.5">
            <Select
              id="allowlist-type"
              label="Observable type"
              value={FIXED_TYPE[kind] ?? observableType}
              onChange={(e) => setObservableType(e.target.value as ObservableType)}
              options={TYPE_OPTIONS}
              placeholder="Select a type"
              disabled={kind !== 'exact'}
              aria-invalid={formErrors.observableType ? true : undefined}
            />
            {formErrors.observableType && (
              <p className="text-xs text-destructive">{formErrors.observableType}</p>
            )}
          </div>
          <Input
            id="allowlist-value"
            label="Value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={KIND_PLACEHOLDERS[kind]}
            className="font-mono"
            error={formErrors.value}
            aria-invalid={formErrors.value ? true : undefined}
            autoFocus
          />
          <Input
            id="allowlist-reason"
            label="Reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g., Corporate DNS resolver"
            maxLength={REASON_MAX_LENGTH}
            error={formErrors.reason}
            aria-invalid={formErrors.reason ? true : undefined}
          />
          {submitError && (
            <p role="alert" className="text-sm text-destructive">
              {submitError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={closeCreateDialog}>
              Cancel
            </Button>
            <Button type="submit" disabled={createEntry.isPending}>
              {createEntry.isPending ? 'Adding...' : 'Add to allowlist'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Remove allowlist entry"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Remove{' '}
            <span className="break-all font-mono font-medium text-foreground">
              {deleteTarget?.value}
            </span>{' '}
            from the allowlist? Observables matched only by this entry will be included in exports
            again immediately. Entries cannot be edited: to change one, remove it and add a new
            entry.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteEntry.isPending}>
              {deleteEntry.isPending ? 'Removing...' : 'Remove entry'}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}

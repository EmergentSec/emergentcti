import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { entityDetailPath, feedsHighlightPath } from '@/lib/safeAppPath'
import {
  useSetTlpOverride,
  useClearTlpOverride,
  useSetObservableTags,
} from '@/hooks/useObservables'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { TlpBadge } from '@/components/common/TlpBadge'
import { TagChips } from '@/components/common/TagChips'
import { TagEditor } from '@/components/common/TagEditor'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Dialog } from '@/components/ui/Dialog'
import { apiErrorMessage } from '@/lib/apiError'
import { formatRelativeTime } from '@/lib/utils'
import { REASON_MAX_LENGTH } from '@/lib/policyValidation'
import { TLP_SELECT_OPTIONS, parseTlpSelectValue, tlpSourceLabel } from '@/lib/tlp'
import type { Observable, Tlp } from '@/types/observable'

interface ObservableTlpPanelProps {
  observable: Observable
  observableId: string
}

export function ObservableTlpPanel({ observable, observableId }: ObservableTlpPanelProps) {
  const { isAdmin } = useAuth()
  const { toast } = useToast()
  const setTlpOverride = useSetTlpOverride()
  const clearTlpOverride = useClearTlpOverride()
  const setTags = useSetObservableTags()

  const [overrideTlp, setOverrideTlp] = useState<Tlp>('amber')
  const [overrideReason, setOverrideReason] = useState('')
  const [overrideError, setOverrideError] = useState<string | null>(null)
  const [tagDraft, setTagDraft] = useState<string[]>(observable.tags)
  const [showClearConfirm, setShowClearConfirm] = useState(false)

  useEffect(() => {
    setTagDraft(observable.tags)
  }, [observable.id, observable.tags])

  const tlpBusy = setTlpOverride.isPending || clearTlpOverride.isPending

  const handleSetOverride = (e: React.FormEvent) => {
    e.preventDefault()
    const reason = overrideReason.trim()
    if (!reason) {
      setOverrideError('Reason is required')
      return
    }
    if (reason.length > REASON_MAX_LENGTH) {
      setOverrideError(`Reason must be ${REASON_MAX_LENGTH} characters or fewer`)
      return
    }
    setOverrideError(null)
    setTlpOverride.mutate(
      { id: observableId, body: { tlp: overrideTlp, reason } },
      {
        onSuccess: () => {
          toast('TLP override set', 'success')
          setOverrideReason('')
        },
        onError: (err) => {
          const message = apiErrorMessage(err, 'Failed to set TLP override')
          setOverrideError(message)
          toast(message, 'error')
        },
      },
    )
  }

  const handleClearOverride = () => {
    setOverrideError(null)
    clearTlpOverride.mutate(observableId, {
      onSuccess: () => {
        toast('TLP override cleared', 'success')
        setShowClearConfirm(false)
      },
      onError: (err) => {
        const message = apiErrorMessage(err, 'Failed to clear TLP override')
        setOverrideError(message)
        toast(message, 'error')
      },
    })
  }

  const handleSaveTags = () => {
    setTags.mutate(
      { id: observableId, tags: tagDraft },
      {
        onSuccess: () => toast('Tags updated', 'success'),
        onError: (err) => toast(apiErrorMessage(err, 'Failed to update tags'), 'error'),
      },
    )
  }

  return (
    <>
      <Card>
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-sm font-semibold">Sharing policy (TLP)</h3>
            <TlpBadge tlp={observable.effective_tlp} className="text-sm" />
          </div>

          {observable.tlp_override && (
            <p className="text-sm text-muted-foreground">
              <TlpBadge tlp={observable.tlp_override.tlp} /> override by{' '}
              {observable.tlp_override.set_by ?? 'an API key or removed user'},{' '}
              {formatRelativeTime(observable.tlp_override.set_at)} — {observable.tlp_override.reason}
            </p>
          )}

          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Why this marking
            </h4>
            {observable.tlp_sources.length === 0 ? (
              <p className="text-sm text-muted-foreground">No contributing sources recorded.</p>
            ) : (
              <ul className="divide-y divide-border rounded-lg border border-border text-sm">
                {observable.tlp_sources.map((source, idx) => (
                  <li key={`${source.kind}-${source.id ?? idx}`} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                    <span>
                      {source.kind === 'feed' && source.id ? (
                        <Link to={feedsHighlightPath(source.id) ?? '/feeds'} className="font-medium hover:text-primary">
                          {tlpSourceLabel(source.kind, source.name)}
                        </Link>
                      ) : source.kind === 'report' && source.id ? (
                        <Link to={entityDetailPath('/reports', source.id) ?? '/reports'} className="font-medium hover:text-primary">
                          {source.name}
                        </Link>
                      ) : (
                        <span className="font-medium">{tlpSourceLabel(source.kind, source.name)}</span>
                      )}
                    </span>
                    <TlpBadge tlp={source.tlp} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          {isAdmin && (
            <form onSubmit={handleSetOverride} noValidate className="space-y-3 border-t border-border pt-4">
              <p className="text-sm font-medium">Admin TLP override</p>
              <p className="text-sm text-muted-foreground">
                Sets an explicit sharing policy for this observable. A reason is always required.
              </p>
              <div className="flex max-w-md flex-col gap-2 sm:flex-row sm:items-end">
                <Select
                  label="Override marking"
                  options={TLP_SELECT_OPTIONS.filter((o) => o.value !== '')}
                  value={overrideTlp}
                  onChange={(e) => setOverrideTlp(parseTlpSelectValue(e.target.value) ?? 'amber')}
                  disabled={tlpBusy}
                  className="sm:flex-1"
                />
                <div className="sm:flex-[2]">
                  <Input
                    id="tlp-override-reason"
                    label="Reason"
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    maxLength={REASON_MAX_LENGTH}
                    error={overrideError ?? undefined}
                    disabled={tlpBusy}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="submit" variant="outline" size="sm" disabled={tlpBusy}>
                    {setTlpOverride.isPending ? 'Setting…' : 'Set TLP override'}
                </Button>
                {observable.tlp_override && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={tlpBusy}
                    onClick={() => setShowClearConfirm(true)}
                  >
                    Clear override
                  </Button>
                )}
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-5">
          <h3 className="text-sm font-semibold">Tags</h3>
          {isAdmin ? (
            <TagEditor
              tags={tagDraft}
              onChange={setTagDraft}
              onSave={handleSaveTags}
              isSaving={setTags.isPending}
            />
          ) : (
            <TagChips tags={observable.tags} emptyLabel="No tags" />
          )}
        </CardContent>
      </Card>

      <Dialog open={showClearConfirm} onClose={() => setShowClearConfirm(false)} title="Clear TLP override?">
        <p className="text-sm text-muted-foreground">
          The effective marking will be recomputed from feeds, linked reports, and manual input.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => setShowClearConfirm(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={handleClearOverride} disabled={clearTlpOverride.isPending}>
            {clearTlpOverride.isPending ? 'Clearing…' : 'Clear override'}
          </Button>
        </div>
      </Dialog>
    </>
  )
}

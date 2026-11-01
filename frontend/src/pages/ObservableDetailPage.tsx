import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  At,
  Check,
  Copy,
  Export,
  Fingerprint,
  Globe,
  GlobeHemisphereWest,
  Icon,
  LinkSimple,
  ShieldCheck,
  TerminalWindow,
} from '@phosphor-icons/react'
import { useObservable, useSetConfidenceOverride, useClearConfidenceOverride } from '@/hooks/useObservables'
import { useObservableReports } from '@/hooks/useReports'
import { useCreateAllowlistEntry } from '@/hooks/useAllowlist'
import { useConfig } from '@/hooks/useConfig'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Tabs } from '@/components/ui/Tabs'
import { ConfidenceRing } from '@/components/observables/ConfidenceRing'
import { DecayChart } from '@/components/observables/DecayChart'
import { DetailSourcesTab } from '@/components/observables/DetailSourcesTab'
import { DetailRawTab } from '@/components/observables/DetailRawTab'
import { jsonExportUrl } from '@/api/export'
import { apiErrorMessage, apiErrorStatus } from '@/lib/apiError'
import {
  CONFIDENCE_OVERRIDE_HELP,
  validateConfidenceOverrideInput,
} from '@/lib/confidenceOverrideValidation'
import { REASON_MAX_LENGTH } from '@/lib/policyValidation'
import { formatDate, formatRelativeTime, typeColors, typeLabels } from '@/lib/utils'
import type { ObservableType } from '@/types/observable'

// ── Type helpers ──────────────────────────────────────────────────────────────

const TYPE_ICONS: Record<ObservableType, Icon> = {
  'ip-addr': GlobeHemisphereWest,
  'domain-name': Globe,
  'url': LinkSimple,
  'file-hash': Fingerprint,
  'email-addr': At,
  'command-line': TerminalWindow,
}

function getBand(score: number): { label: string; cssVar: string } {
  if (score >= 80) return { label: 'Critical', cssVar: 'var(--conf-critical)' }
  if (score >= 60) return { label: 'High', cssVar: 'var(--conf-high)' }
  if (score >= 40) return { label: 'Medium', cssVar: 'var(--conf-medium)' }
  return { label: 'Low', cssVar: 'var(--conf-low)' }
}

// ── Page ──────────────────────────────────────────────────────────────────────

const DECAY_DEFAULTS = { days: 30, rate: 5, floor: 10 }

const DETAIL_TABS = [
  { key: 'sources', label: 'Sources' },
  { key: 'raw', label: 'Raw JSON' },
]

export default function ObservableDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: obs, isLoading, error } = useObservable(id ?? null)
  const { data: linkedReports = [], isLoading: reportsLoading } = useObservableReports(id ?? null)
  const { data: cfg } = useConfig()
  const [searchParams, setSearchParams] = useSearchParams()
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState(() => searchParams.get('tab') === 'raw' ? 'raw' : 'sources')
  const { isAdmin } = useAuth()
  const { toast } = useToast()
  const createAllowlistEntry = useCreateAllowlistEntry()
  const setConfidenceOverride = useSetConfidenceOverride()
  const clearConfidenceOverride = useClearConfidenceOverride()
  const [showAllowlist, setShowAllowlist] = useState(false)
  const [allowlistReason, setAllowlistReason] = useState('')
  const [allowlistError, setAllowlistError] = useState<string | null>(null)
  const [overrideInput, setOverrideInput] = useState('')
  const [overrideError, setOverrideError] = useState<string | null>(null)

  useEffect(() => {
    if (obs) {
      setOverrideInput(String(obs.confidence_score))
      setOverrideError(null)
    }
  }, [obs?.id, obs?.confidence_score])

  useEffect(() => {
    const tab = searchParams.get('tab')
    setActiveTab(tab === 'raw' ? 'raw' : 'sources')
  }, [searchParams])

  const handleTabChange = (tab: string) => {
    setActiveTab(tab)
    const next = new URLSearchParams(searchParams)
    if (tab === 'raw') next.set('tab', 'raw')
    else next.delete('tab')
    setSearchParams(next, { replace: true })
  }

  const closeAllowlistDialog = () => {
    setShowAllowlist(false)
    setAllowlistReason('')
    setAllowlistError(null)
  }

  const handleAllowlist = (e: React.FormEvent) => {
    e.preventDefault()
    if (!obs) return
    const reason = allowlistReason.trim()
    if (!reason) {
      setAllowlistError('Reason is required')
      return
    }
    setAllowlistError(null)
    createAllowlistEntry.mutate(
      {
        kind: obs.type === 'ip-addr' && obs.value.includes('/') ? 'cidr' : 'exact',
        value: obs.value,
        observable_type: obs.type,
        reason,
      },
      {
        onSuccess: () => {
          toast(`${obs.value} added to the allowlist`, 'success')
          closeAllowlistDialog()
        },
        onError: (err) => {
          const message =
            apiErrorStatus(err) === 409
              ? 'This value is already on the allowlist.'
              : apiErrorMessage(err, 'Failed to add allowlist entry')
          setAllowlistError(message)
          toast(message, 'error')
        },
      },
    )
  }

  const handleCopy = () => {
    if (!obs) return
    navigator.clipboard.writeText(obs.value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    }).catch(() => {})
  }

  const handleSetOverride = (e: React.FormEvent) => {
    e.preventDefault()
    if (!obs || !id) return
    const parsed = validateConfidenceOverrideInput(overrideInput)
    if (!parsed.ok) {
      setOverrideError(parsed.message)
      return
    }
    setOverrideError(null)
    setConfidenceOverride.mutate(
      { id, confidence: parsed.value },
      {
        onSuccess: () => {
          toast('Confidence override set', 'success')
        },
        onError: (err) => {
          const message = apiErrorMessage(err, 'Failed to set confidence override')
          setOverrideError(message)
          toast(message, 'error')
        },
      },
    )
  }

  const handleClearOverride = () => {
    if (!obs || !id) return
    const confirmed = window.confirm(
      'Clear the pinned override? Confidence will be recomputed from feeds and analyst decisions.',
    )
    if (!confirmed) return
    setOverrideError(null)
    clearConfidenceOverride.mutate(id, {
      onSuccess: () => {
        toast('Confidence override cleared', 'success')
      },
      onError: (err) => {
        const message = apiErrorMessage(err, 'Failed to clear confidence override')
        setOverrideError(message)
        toast(message, 'error')
      },
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !obs) {
    return (
      <EmptyState
        className="[&_h3]:text-destructive"
        title="Failed to load observable"
        description={error instanceof Error ? error.message : 'Observable not found'}
      />
    )
  }

  const TypeIcon = TYPE_ICONS[obs.type]
  const band = getBand(obs.confidence_score)
  const nativeMax = obs.sources.length > 0
    ? Math.max(obs.confidence_score, ...obs.sources.map((source) => source.native_confidence))
    : obs.confidence_score
  const ageDays = obs.last_seen
    ? Math.floor((Date.now() - new Date(obs.last_seen).getTime()) / 86_400_000)
    : 0
  const decayDays = cfg?.confidence_decay_days ?? DECAY_DEFAULTS.days
  const decayRate = cfg?.confidence_decay_rate ?? DECAY_DEFAULTS.rate
  const decayFloor = cfg?.confidence_decay_floor ?? DECAY_DEFAULTS.floor

  return (
    <div className="space-y-4">
      {/* ── Back link ──────────────────────────────────────────────── */}
      <Link
        to="/observables"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft size={14} />
        Observables
      </Link>

      {/* ── Header card ────────────────────────────────────────────── */}
      <Card>
        <CardContent className="p-5">
        {/* Top row: icon tile + type/value/copy + action buttons */}
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
          {/* Type icon tile */}
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border ${typeColors[obs.type]}`}>
            <TypeIcon size={24} weight="duotone" />
          </div>

          {/* Type chip + confidence chip + large mono value + copy */}
          <div className="min-w-0 flex-1">
            {/* Chips */}
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={typeColors[obs.type]}>
                {typeLabels[obs.type] ?? obs.type}
              </Badge>
              <Badge variant="secondary" style={{ color: band.cssVar }}>
                {band.label} confidence
              </Badge>
              {obs.allowlisted && (
                <Badge
                  variant="outline"
                  className="rounded-md text-muted-foreground"
                  title="Allowlisted — excluded from exports"
                >
                  Allowlisted
                </Badge>
              )}
              {obs.confidence_override && (
                <Badge variant="warning" title="Confidence is pinned by an admin override">
                  Pinned by {obs.confidence_override.set_by ?? 'deleted user'},{' '}
                  {formatRelativeTime(obs.confidence_override.set_at)}
                </Badge>
              )}
            </div>

            {/* Value + copy button */}
            <div className="flex min-w-0 items-start gap-2">
              <span className="min-w-0 break-all font-mono text-xl font-semibold tracking-tight sm:text-2xl">
                {obs.value}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label="Copy value"
                onClick={handleCopy}
                className="h-8 w-8 px-0 text-muted-foreground"
              >
                {copied ? <Check size={14} weight="bold" /> : <Copy size={14} />}
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {obs.allowlisted ? (
                <Link
                  to="/settings?tab=allowlist"
                  className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                >
                  Manage allowlist
                </Link>
              ) : (
                isAdmin && (
                  <Button variant="outline" size="sm" onClick={() => setShowAllowlist(true)}>
                    <ShieldCheck size={14} />
                    Allowlist
                  </Button>
                )
              )}
              <a
                href={jsonExportUrl({ type: obs.type })}
                download
                className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <Export size={14} />
                Export
              </a>
            </div>
          </div>

          <div className="shrink-0 self-center rounded-xl bg-surface2 p-3 sm:self-start">
            <ConfidenceRing decayed={obs.confidence_score} nativeMax={nativeMax} compact />
          </div>
        </div>

        {/* ── 4-cell key-facts strip ─────────────────────────────── */}
        <div className="mt-5 grid grid-cols-2 overflow-hidden rounded-lg border border-border bg-surface2 sm:grid-cols-4 sm:divide-x sm:divide-border">
          {/* FIRST SEEN */}
          <div className="border-b border-border px-4 py-3 sm:border-b-0">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              First Seen
            </p>
            <p className="font-mono text-sm font-semibold">{formatDate(obs.first_seen)}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{formatRelativeTime(obs.first_seen)}</p>
          </div>

          {/* LAST SEEN */}
          <div className="border-b border-l border-border px-4 py-3 sm:border-b-0 sm:border-l-0">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Last Seen
            </p>
            <p className="font-mono text-sm font-semibold">{formatDate(obs.last_seen)}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{formatRelativeTime(obs.last_seen)}</p>
          </div>

          {/* SOURCES */}
          <div className="px-4 py-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Sources
            </p>
            <p className="font-mono text-sm font-semibold">{obs.source_count}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">feeds reporting</p>
          </div>

          {/* CONFIDENCE */}
          <div className="border-l border-border px-4 py-3 sm:border-l-0">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Confidence
            </p>
            <p className="font-mono text-sm font-semibold">{obs.confidence_score}</p>
            <p className="mt-0.5 text-xs" style={{ color: band.cssVar }}>
              {band.label} band
            </p>
          </div>
        </div>
        </CardContent>
      </Card>

      {(obs.manual_confidence != null || (isAdmin && id)) && (
        <Card>
          <CardContent className="space-y-4 p-5">
            <div>
              <h3 className="text-sm font-semibold">Analyst confidence</h3>
              {obs.manual_confidence != null && (
                <p className="mt-1 text-sm text-muted-foreground">
                  Analyst floor:{' '}
                  <span className="font-mono font-medium text-foreground">{obs.manual_confidence}</span>
                </p>
              )}
            </div>
            {isAdmin && id && (
              <form onSubmit={handleSetOverride} noValidate className="space-y-3">
                <p className="text-sm font-medium">Override confidence</p>
                <p className="text-sm text-muted-foreground">{CONFIDENCE_OVERRIDE_HELP}</p>
                <div className="flex max-w-xs flex-col gap-2 sm:flex-row sm:items-end">
                  <Input
                    id="confidence-override"
                    label="Confidence (0–100)"
                    type="text"
                    inputMode="numeric"
                    value={overrideInput}
                    onChange={(e) => setOverrideInput(e.target.value)}
                    aria-invalid={overrideError ? true : undefined}
                    className="sm:flex-1"
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="submit"
                      variant="outline"
                      size="sm"
                      disabled={setConfidenceOverride.isPending}
                    >
                      {setConfidenceOverride.isPending ? 'Setting…' : 'Set override'}
                    </Button>
                    {obs.confidence_override && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={clearConfidenceOverride.isPending}
                        onClick={handleClearOverride}
                      >
                        {clearConfidenceOverride.isPending ? 'Clearing…' : 'Clear override'}
                      </Button>
                    )}
                  </div>
                </div>
                {overrideError && (
                  <p role="alert" className="text-sm text-destructive">
                    {overrideError}
                  </p>
                )}
              </form>
            )}
          </CardContent>
        </Card>
      )}

      <DecayChart
        nativeMax={nativeMax}
        ageDays={ageDays}
        decayDays={decayDays}
        decayRate={decayRate}
        decayFloor={decayFloor}
      />

      <Card className="p-5">
        <h3 className="mb-3 text-sm font-semibold">Reports</h3>
        {reportsLoading ? (
          <LoadingSpinner size="sm" />
        ) : linkedReports.length === 0 ? (
          <p className="text-sm text-muted-foreground">No linked reports.</p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {linkedReports.map((report) => (
              <li key={report.id} className="px-3 py-2.5">
                <Link
                  to={`/reports/${report.id}`}
                  className="font-medium text-foreground hover:text-primary"
                >
                  {report.title}
                </Link>
                {report.summary && (
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{report.summary}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── Sources / Raw JSON tabs ─────────────────────────────────── */}
      <Card className="p-5">
        <Tabs tabs={DETAIL_TABS} active={activeTab} onChange={handleTabChange} className="mb-4" />
        {activeTab === 'sources' && <DetailSourcesTab sources={obs.sources} />}
        {activeTab === 'raw' && <DetailRawTab observable={obs} />}
      </Card>

      {/* ── Allowlist exact value dialog (admin) ────────────────────── */}
      <Dialog open={showAllowlist} onClose={closeAllowlistDialog} title="Allowlist this value">
        <form onSubmit={handleAllowlist} noValidate className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Adds {obs.type === 'ip-addr' && obs.value.includes('/') ? 'a CIDR entry' : 'an exact-value entry'} for{' '}
            <span className="break-all font-mono font-medium text-foreground">{obs.value}</span>{' '}
            ({typeLabels[obs.type] ?? obs.type}). The observable and its sources are kept; it is
            only left out of exports, and removing the entry in Settings reverses this
            immediately. Allowlisting does not protect it from retention deletion.
            {obs.type === 'ip-addr' && obs.value.includes('/') && (
              <> The CIDR policy also suppresses other IP indicators overlapping this range.</>
            )}
          </p>
          <Input
            id="allowlist-reason"
            label="Reason"
            value={allowlistReason}
            onChange={(e) => setAllowlistReason(e.target.value)}
            placeholder="e.g., Corporate DNS resolver"
            maxLength={REASON_MAX_LENGTH}
            aria-invalid={allowlistError ? true : undefined}
            autoFocus
          />
          {allowlistError && (
            <p role="alert" className="text-sm text-destructive">
              {allowlistError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={closeAllowlistDialog}>
              Cancel
            </Button>
            <Button type="submit" disabled={createAllowlistEntry.isPending}>
              {createAllowlistEntry.isPending ? 'Adding...' : 'Add to allowlist'}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}

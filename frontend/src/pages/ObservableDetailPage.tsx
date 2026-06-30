import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
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
  Prohibit,
  TerminalWindow,
} from '@phosphor-icons/react'
import { useObservable } from '@/hooks/useObservables'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { jsonExportUrl } from '@/api/export'
import { cn, formatDate, formatRelativeTime, typeLabels } from '@/lib/utils'
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

const TYPE_CAT_VAR: Record<ObservableType, string> = {
  'ip-addr': 'var(--cat-blue)',
  'domain-name': 'var(--cat-purple)',
  'url': 'var(--cat-green)',
  'file-hash': 'var(--cat-orange)',
  'email-addr': 'var(--cat-pink)',
  'command-line': 'var(--cat-yellow)',
}

function getBand(score: number): { label: string; cssVar: string } {
  if (score >= 80) return { label: 'Critical', cssVar: 'var(--conf-critical)' }
  if (score >= 60) return { label: 'High', cssVar: 'var(--conf-high)' }
  if (score >= 40) return { label: 'Medium', cssVar: 'var(--conf-medium)' }
  return { label: 'Low', cssVar: 'var(--conf-low)' }
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ObservableDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: obs, isLoading, error } = useObservable(id ?? null)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!obs) return
    navigator.clipboard.writeText(obs.value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
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
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-destructive-foreground">Failed to load observable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {error instanceof Error ? error.message : 'Observable not found'}
        </p>
      </div>
    )
  }

  const TypeIcon = TYPE_ICONS[obs.type]
  const catColor = TYPE_CAT_VAR[obs.type] ?? 'var(--cat-blue)'
  const band = getBand(obs.confidence_score)

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
      <Card className="p-5">
        {/* Top row: icon tile + type/value/copy + action buttons */}
        <div className="flex items-start gap-4">
          {/* Type icon tile */}
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg"
            style={{
              background: `color-mix(in srgb, ${catColor} 14%, transparent)`,
              color: catColor,
            }}
          >
            <TypeIcon size={24} weight="duotone" />
          </div>

          {/* Type chip + confidence chip + large mono value + copy */}
          <div className="min-w-0 flex-1">
            {/* Chips */}
            <div className="mb-1.5 flex items-center gap-2">
              <span
                className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium"
                style={{
                  background: `color-mix(in srgb, ${catColor} 14%, transparent)`,
                  color: catColor,
                }}
              >
                {typeLabels[obs.type] ?? obs.type}
              </span>
              <span
                className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-medium"
                style={{ color: band.cssVar }}
              >
                {band.label} confidence
              </span>
            </div>

            {/* Value + copy button */}
            <div className="flex items-center gap-2">
              <span className="break-all font-mono text-2xl font-semibold tracking-tight">
                {obs.value}
              </span>
              <button
                type="button"
                aria-label="Copy value"
                onClick={handleCopy}
                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-input bg-transparent text-muted-foreground transition-colors hover:text-foreground"
              >
                {copied ? <Check size={14} weight="bold" /> : <Copy size={14} />}
              </button>
            </div>
          </div>

          {/* Right-aligned action buttons */}
          <div className="flex shrink-0 items-center gap-2 pt-1">
            <Button
              variant="outline"
              size="sm"
              disabled
              title="Blocklisting is handled via blocklist export"
            >
              <Prohibit size={14} className="mr-1.5" />
              Block
            </Button>
            <a
              href={jsonExportUrl({ type: obs.type })}
              download
              className={cn(
                'inline-flex items-center justify-center gap-1.5 font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                'focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                'bg-brand text-brand-foreground hover:bg-brand/90',
                'h-8 rounded-sm px-3 text-xs',
              )}
            >
              <Export size={14} />
              Export
            </a>
          </div>
        </div>

        {/* ── 4-cell key-facts strip ─────────────────────────────── */}
        <div className="mt-5 grid grid-cols-4 divide-x divide-border overflow-hidden rounded-lg border border-border">
          {/* FIRST SEEN */}
          <div className="px-4 py-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              First Seen
            </p>
            <p className="font-mono text-sm font-semibold">{formatDate(obs.first_seen)}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{formatRelativeTime(obs.first_seen)}</p>
          </div>

          {/* LAST SEEN */}
          <div className="px-4 py-3">
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
          <div className="px-4 py-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Confidence
            </p>
            <p className="font-mono text-sm font-semibold">{obs.confidence_score}</p>
            <p className="mt-0.5 text-xs" style={{ color: band.cssVar }}>
              {band.label} band
            </p>
          </div>
        </div>
      </Card>

      {/* ── Placeholder for decay ring + tabs (next batch) ─────────── */}
      <div data-testid="detail-placeholder">
        {/* decay + tabs added in next batch */}
      </div>
    </div>
  )
}

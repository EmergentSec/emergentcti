import { useNavigate } from 'react-router-dom'
import {
  At,
  CaretRight,
  Fingerprint,
  Globe,
  GlobeHemisphereWest,
  Icon,
  LinkSimple,
  TerminalWindow,
  Trash,
} from '@phosphor-icons/react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useDeleteObservable } from '@/hooks/useObservables'
import { typeLabels, formatRelativeTime } from '@/lib/utils'
import type { Observable, ObservableSource, ObservableType } from '@/types/observable'

interface ObservableTableProps {
  observables: Observable[]
}

// ---------------------------------------------------------------------------
// Type chip helpers
// ---------------------------------------------------------------------------

const TYPE_ICONS: Record<string, Icon> = {
  'ip-addr': GlobeHemisphereWest,
  'domain-name': Globe,
  'url': LinkSimple,
  'file-hash': Fingerprint,
  'email-addr': At,
  'command-line': TerminalWindow,
}

// CSS variable for each type's categorical token
const TYPE_CAT_VAR: Record<string, string> = {
  'ip-addr': 'var(--cat-blue)',
  'domain-name': 'var(--cat-purple)',
  'url': 'var(--cat-green)',
  'file-hash': 'var(--cat-orange)',
  'email-addr': 'var(--cat-pink)',
  'command-line': 'var(--cat-yellow)',
}

function TypeChip({ type }: { type: ObservableType }) {
  const Icon = TYPE_ICONS[type]
  const catColor = TYPE_CAT_VAR[type] ?? 'var(--cat-blue)'
  const label = typeLabels[type] ?? type

  return (
    <span
      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap"
      style={{
        background: `color-mix(in srgb, ${catColor} 14%, transparent)`,
        color: catColor,
      }}
    >
      {Icon && <Icon size={12} weight="bold" />}
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Confidence band helpers
// ---------------------------------------------------------------------------

function getBand(score: number): { label: string; color: string } {
  if (score >= 80) return { label: 'Critical', color: 'var(--conf-critical)' }
  if (score >= 60) return { label: 'High', color: 'var(--conf-high)' }
  if (score >= 40) return { label: 'Medium', color: 'var(--conf-medium)' }
  return { label: 'Low', color: 'var(--conf-low)' }
}

function ConfidenceBar({ score }: { score: number }) {
  const { label, color } = getBand(score)

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 flex-shrink-0 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="font-mono text-xs tabular-nums" style={{ color }}>
        {score}
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Source chips
// ---------------------------------------------------------------------------

function SourceChips({ sources }: { sources: ObservableSource[] }) {
  if (sources.length === 0) {
    return (
      <span className="inline-flex items-center rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
        Manual
      </span>
    )
  }

  const shown = sources.slice(0, 2)
  const overflow = sources.length - 2

  return (
    <span className="inline-flex flex-wrap gap-1">
      {shown.map((s) => (
        <span
          key={s.feed_id}
          className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-xs"
        >
          {s.feed_name}
        </span>
      ))}
      {overflow > 0 && (
        <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
          +{overflow}
        </span>
      )}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main table
// ---------------------------------------------------------------------------

export function ObservableTable({ observables }: ObservableTableProps) {
  const navigate = useNavigate()
  const deleteObservable = useDeleteObservable()

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-36">Type</TableHead>
          <TableHead>Value</TableHead>
          <TableHead className="w-48">Confidence</TableHead>
          <TableHead className="w-52">Sources</TableHead>
          <TableHead className="w-28 text-right">Last Seen</TableHead>
          {/* delete + caret — no header labels */}
          <TableHead className="w-10" />
          <TableHead className="w-8" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {observables.map((obs) => (
          <TableRow
            key={obs.id}
            className="group cursor-pointer hover:bg-hover transition-colors"
            tabIndex={0}
            role="button"
            aria-label={`View details for ${obs.value}`}
            onClick={() => navigate(`/observables/${obs.id}`)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                navigate(`/observables/${obs.id}`)
              }
            }}
          >
            {/* TYPE */}
            <TableCell>
              <TypeChip type={obs.type} />
            </TableCell>

            {/* VALUE — mono, truncated */}
            <TableCell className="font-mono text-sm max-w-[22rem] truncate">
              {obs.value}
            </TableCell>

            {/* CONFIDENCE */}
            <TableCell>
              <ConfidenceBar score={obs.confidence_score} />
            </TableCell>

            {/* SOURCES */}
            <TableCell>
              <SourceChips sources={obs.sources} />
            </TableCell>

            {/* LAST SEEN */}
            <TableCell className="text-right text-sm text-muted-foreground whitespace-nowrap">
              {formatRelativeTime(obs.last_seen)}
            </TableCell>

            {/* DELETE — hover-only, stops propagation */}
            <TableCell className="text-right">
              <button
                className="opacity-0 group-hover:opacity-100 transition-opacity rounded p-1 text-muted-foreground hover:text-destructive focus:opacity-100"
                aria-label={`Delete ${obs.value}`}
                disabled={deleteObservable.isPending}
                onClick={(e) => {
                  e.stopPropagation()
                  if (!window.confirm(`Delete observable "${obs.value}"?`)) return
                  deleteObservable.mutate(obs.id)
                }}
              >
                <Trash size={14} />
              </button>
            </TableCell>

            {/* CARET */}
            <TableCell className="text-muted-foreground">
              <CaretRight size={14} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

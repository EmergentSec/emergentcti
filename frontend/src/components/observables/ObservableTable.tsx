import { useNavigate } from 'react-router-dom'
import {
  At,
  CaretRight,
  Fingerprint,
  Globe,
  GlobeHemisphereWest,
  Icon,
  LinkSimple,
  PushPin,
  TerminalWindow,
  Trash,
} from '@phosphor-icons/react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ConfidenceMeter } from '@/components/common/ConfidenceMeter'
import { TlpBadge } from '@/components/common/TlpBadge'
import { TagChips } from '@/components/common/TagChips'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useDeleteObservable } from '@/hooks/useObservables'
import { useAuth } from '@/contexts/AuthContext'
import { typeColors, typeLabels, formatRelativeTime } from '@/lib/utils'
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

function TypeChip({ type }: { type: ObservableType }) {
  const Icon = TYPE_ICONS[type]
  const label = typeLabels[type] ?? type

  return (
    <Badge variant="outline" className={typeColors[type]}>
      {Icon && <Icon size={12} weight="bold" />}
      {label}
    </Badge>
  )
}

// ---------------------------------------------------------------------------
// Source chips
// ---------------------------------------------------------------------------

function SourceChips({ sources }: { sources: ObservableSource[] }) {
  if (sources.length === 0) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Manual
      </Badge>
    )
  }

  const shown = sources.slice(0, 2)
  const overflowCount = Math.max(0, sources.length - 2)

  return (
    <span className="inline-flex flex-wrap gap-1">
      {shown.map((s) => (
        <Badge key={s.feed_id} variant="secondary">
          {s.feed_name}
        </Badge>
      ))}
      {overflowCount > 0 && (
        <Badge variant="secondary">
          +{overflowCount}
        </Badge>
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
  const { isAdmin } = useAuth()

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-36">Type</TableHead>
          <TableHead>Value</TableHead>
          <TableHead className="w-36">TLP</TableHead>
          <TableHead className="w-40">Tags</TableHead>
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
            <TableCell className="max-w-[22rem]">
              <div className="flex items-center gap-2">
                <span className="truncate font-mono text-sm">{obs.value}</span>
                {obs.allowlisted && (
                  <Badge
                    variant="outline"
                    className="shrink-0 text-muted-foreground"
                    title="Allowlisted — excluded from exports"
                  >
                    Allowlisted
                  </Badge>
                )}
              </div>
            </TableCell>

            <TableCell>
              <TlpBadge tlp={obs.effective_tlp} />
            </TableCell>

            <TableCell>
              <TagChips tags={obs.tags ?? []} />
            </TableCell>

            {/* CONFIDENCE */}
            <TableCell>
              <span className="inline-flex items-center gap-1.5">
                <ConfidenceMeter score={obs.confidence_score} />
                {obs.confidence_override && (
                  <span title="Pinned confidence override">
                    <PushPin
                      size={14}
                      weight="fill"
                      className="shrink-0 text-warning-ink"
                      aria-label="Pinned confidence override"
                    />
                  </span>
                )}
              </span>
            </TableCell>

            {/* SOURCES */}
            <TableCell>
              <SourceChips sources={obs.sources} />
            </TableCell>

            {/* LAST SEEN */}
            <TableCell className="text-right text-sm text-muted-foreground whitespace-nowrap">
              {formatRelativeTime(obs.last_seen)}
            </TableCell>

            {/* DELETE — admin-only, hover-only, stops propagation */}
            <TableCell className="text-right">
              {isAdmin && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-8 px-0 text-muted-foreground opacity-0 transition-opacity hover:text-destructive focus:opacity-100 group-hover:opacity-100"
                  aria-label={`Delete ${obs.value}`}
                  disabled={deleteObservable.isPending}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!window.confirm(`Delete observable "${obs.value}"?`)) return
                    deleteObservable.mutate(obs.id)
                  }}
                >
                  <Trash size={14} />
                </Button>
              )}
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

import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { TLP_LABELS, TLP_MEANINGS, TLP_UNSPECIFIED_MEANING } from '@/lib/tlp'
import type { Tlp } from '@/types/tlp'

export interface TlpBadgeProps {
  tlp: Tlp | null
  /** When true, show a compact STRICT suffix for amber+strict (default true). */
  showStrictLabel?: boolean
  className?: string
}

function badgeClasses(tlp: Tlp | null): string {
  if (tlp === null) {
    return cn(
      'border border-dashed border-muted-foreground/75 bg-transparent text-muted-foreground',
      'dark:border-muted-foreground/50',
    )
  }
  switch (tlp) {
    case 'clear':
      return cn(
        'border border-borderStrong bg-white text-foreground',
        'dark:bg-zinc-100 dark:text-zinc-900',
      )
    case 'green':
      return 'border border-emerald-700/40 bg-emerald-100 text-emerald-950 dark:bg-emerald-950/50 dark:text-emerald-100'
    case 'amber':
      return 'border border-amber-700/40 bg-amber-100 text-amber-950 dark:bg-amber-950/50 dark:text-amber-100'
    case 'amber+strict':
      return 'border border-amber-800/50 bg-amber-200 text-amber-950 dark:bg-amber-900/60 dark:text-amber-50'
    case 'red':
      return 'border border-red-800/40 bg-red-100 text-red-950 dark:bg-red-950/50 dark:text-red-100'
    default:
      return 'border border-border bg-surface2 text-foreground'
  }
}

function labelText(tlp: Tlp | null, showStrictLabel: boolean): ReactNode {
  if (tlp === null) return 'Unspecified'
  if (tlp === 'amber+strict' && showStrictLabel) {
    return (
      <>
        {TLP_LABELS[tlp]}
        <span className="ml-1 font-semibold uppercase tracking-wide">STRICT</span>
      </>
    )
  }
  return TLP_LABELS[tlp]
}

export function TlpBadge({ tlp, showStrictLabel = true, className }: TlpBadgeProps) {
  const meaningId = useId()
  const meaning = tlp === null ? TLP_UNSPECIFIED_MEANING : TLP_MEANINGS[tlp]
  const textLabel = tlp === null ? 'Unspecified' : TLP_LABELS[tlp]

  return (
    <button
      type="button"
      className={cn(
        'inline-flex cursor-default items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium',
        badgeClasses(tlp),
        className,
      )}
      aria-label={textLabel}
      aria-describedby={meaningId}
    >
      {labelText(tlp, showStrictLabel)}
      <span id={meaningId} className="sr-only">
        {meaning}
      </span>
    </button>
  )
}

import { useState } from 'react'
import { Check, Copy } from '@phosphor-icons/react'
import type { Observable } from '@/types/observable'

interface DetailRawTabProps {
  observable: Observable
}

export function DetailRawTab({ observable }: DetailRawTabProps) {
  const [copied, setCopied] = useState(false)
  const json = JSON.stringify(observable, null, 2)

  function handleCopy() {
    navigator.clipboard.writeText(json)
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }

  return (
    <div className="space-y-3">
      {/* Header row: endpoint label + copy button */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-muted-foreground">
          GET /api/v1/observables/:id
        </span>
        <button
          onClick={handleCopy}
          aria-label="Copy JSON"
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:bg-hover hover:text-foreground transition-colors"
        >
          {copied ? <Check size={13} weight="bold" /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      {/* Scrollable JSON block */}
      <div className="rounded-lg bg-surface2 dark:bg-surface3 overflow-auto p-4 max-h-[28rem]">
        <pre className="font-mono text-xs leading-relaxed text-foreground whitespace-pre">
          {json}
        </pre>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Check, Copy } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import type { Observable } from '@/types/observable'

interface DetailRawTabProps {
  observable: Observable
}

export function DetailRawTab({ observable }: DetailRawTabProps) {
  const [copied, setCopied] = useState(false)
  const json = JSON.stringify(observable, null, 2)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(json)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch {
      // clipboard write failed — do not set copied
    }
  }

  return (
    <div className="space-y-3">
      {/* Header row: endpoint label + copy button */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-muted-foreground">
          GET /api/v1/observables/:id
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleCopy}
          aria-label="Copy JSON"
          className="text-muted-foreground"
        >
          {copied ? <Check size={13} weight="bold" /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>

      {/* Scrollable JSON block */}
      <div className="max-h-[28rem] overflow-auto rounded-lg border border-border bg-surface2 p-4">
        <pre className="font-mono text-xs leading-relaxed text-foreground whitespace-pre">
          {json}
        </pre>
      </div>
    </div>
  )
}

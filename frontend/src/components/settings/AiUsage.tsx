import { useState } from 'react'
import { Info } from '@phosphor-icons/react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useAiUsage, useAiUsageRecords } from '@/hooks/useAiUsage'
import { aiRequestErrorMessage, describeAiCategory } from '@/lib/aiErrors'
import { AI_USAGE_SCOPE_LINE } from '@/lib/aiCopy'
import {
  currentUtcMonth,
  displayTokenCount,
  displayUnknown,
  displayUsdEstimate,
  displayUsageSource,
  formatUtcMonthLabel,
} from '@/lib/aiDisplay'
import type { UsageTotals } from '@/types/ai'

function TotalsSummary({ totals }: { totals: UsageTotals }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div>
        <dt className="text-xs text-muted-foreground">Requests</dt>
        <dd className="text-sm font-medium text-foreground">{totals.requests}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Estimated cost</dt>
        <dd className="text-sm font-medium text-foreground">{displayUsdEstimate(totals.estimated_cost_usd)}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Committed (budget)</dt>
        <dd className="text-sm font-medium text-foreground">{displayUsdEstimate(totals.committed_usd)}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Input tokens (known)</dt>
        <dd className="text-sm font-medium text-foreground">{totals.input_tokens}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Output tokens (known)</dt>
        <dd className="text-sm font-medium text-foreground">{totals.output_tokens}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Token usage unknown</dt>
        <dd className="text-sm font-medium text-foreground">{totals.token_unknown_requests} requests</dd>
      </div>
    </dl>
  )
}

function BudgetBar({ committed, budget }: { committed: string; budget: string | null }) {
  if (budget === null) {
    return <p className="text-sm text-muted-foreground">No budget set</p>
  }
  const committedNum = Number(committed)
  const budgetNum = Number(budget)
  const ratio = Number.isFinite(committedNum) && Number.isFinite(budgetNum) && budgetNum > 0
    ? Math.min(100, (committedNum / budgetNum) * 100)
    : 0
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Committed {displayUsdEstimate(committed)}</span>
        <span>Budget {displayUsdEstimate(budget)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface2" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(ratio)} aria-label="Budget committed">
        <div className="h-full bg-primary transition-all" style={{ width: `${ratio}%` }} />
      </div>
    </div>
  )
}

function breakdownRows(label: string, rows: ({ provider?: string; model?: string; date?: string } & UsageTotals)[]) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">{label}</h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Key</TableHead>
            <TableHead>Requests</TableHead>
            <TableHead>Est. cost</TableHead>
            <TableHead>Committed</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const key =
              row.date ??
              (row.provider && row.model ? `${row.provider} / ${row.model}` : displayUnknown(null))
            return (
              <TableRow key={key}>
                <TableCell className="font-mono text-xs">{key}</TableCell>
                <TableCell>{row.requests}</TableCell>
                <TableCell>{displayUsdEstimate(row.estimated_cost_usd)}</TableCell>
                <TableCell>{displayUsdEstimate(row.committed_usd)}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

export function AiUsagePanel() {
  const [month, setMonth] = useState(currentUtcMonth())
  const usage = useAiUsage(month)
  const records = useAiUsageRecords(month)

  return (
    <Card>
      <section aria-labelledby="ai-usage-title" className="space-y-4 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 id="ai-usage-title" className="text-base font-semibold text-foreground">
              AI usage
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {formatUtcMonthLabel(month)}, {AI_USAGE_SCOPE_LINE}
            </p>
          </div>
          <Input
            id="ai-usage-month"
            label="Month (UTC)"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        </div>

        <div className="flex gap-3 rounded-xl border border-border bg-surface2 p-4">
          <Info size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-primary" />
          <p className="text-sm text-muted-foreground">
            Costs shown here are local estimates from admin-entered pricing, not provider invoices.
          </p>
        </div>

        {usage.isLoading ? (
          <div className="flex justify-center py-6">
            <LoadingSpinner />
          </div>
        ) : usage.error ? (
          <p className="text-sm text-destructive">{aiRequestErrorMessage(usage.error, "Couldn't load usage.")}</p>
        ) : usage.data ? (
          <div className="space-y-6">
            <BudgetBar committed={usage.data.budget.committed_usd} budget={usage.data.budget.monthly_budget_usd} />
            {usage.data.budget.remaining_usd !== null && (
              <p className="text-sm text-muted-foreground">
                Remaining budget estimate: {displayUsdEstimate(usage.data.budget.remaining_usd)}
              </p>
            )}
            <TotalsSummary totals={usage.data.totals} />
            {usage.data.totals.cost_unknown_requests > 0 && (
              <p className="text-sm text-warning-ink">
                {usage.data.totals.cost_unknown_requests} requests with unknown cost
              </p>
            )}
            {breakdownRows('By provider and model', usage.data.by_provider_model)}
            {breakdownRows('By day', usage.data.by_day)}
          </div>
        ) : null}

        <div className="space-y-2 border-t border-border pt-4">
          <h4 className="text-sm font-medium text-foreground">Recent records</h4>
          {records.isLoading ? (
            <LoadingSpinner />
          ) : records.error ? (
            <p className="text-sm text-destructive">{aiRequestErrorMessage(records.error, "Couldn't load records.")}</p>
          ) : records.data && records.data.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {records.data.items.map((rec) => (
                  <TableRow key={rec.id}>
                    <TableCell className="text-xs">{rec.started_at}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {rec.provider}/{rec.model}
                    </TableCell>
                    <TableCell>
                      <Badge variant={rec.status === 'succeeded' ? 'success' : rec.status === 'failed' ? 'destructive' : 'secondary'}>
                        {rec.status}
                        {rec.stale ? ' (stale)' : ''}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      {displayTokenCount(rec.input_tokens)} / {displayTokenCount(rec.output_tokens)} ({displayUsageSource(rec.usage_source)})
                    </TableCell>
                    <TableCell className="text-xs">
                      {displayUsdEstimate(rec.cost_usd)}
                      {rec.error_category && (
                        <span className="block text-muted-foreground">{describeAiCategory(rec.error_category)}</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No usage records for this month.</p>
          )}
        </div>
      </section>
    </Card>
  )
}

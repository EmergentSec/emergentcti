import { useState } from 'react'
import { Info } from '@phosphor-icons/react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useAiUsage, useAiUsageRecords } from '@/hooks/useAiUsage'
import { aiRequestErrorMessage, describeAiCategory } from '@/lib/aiErrors'
import { AI_USAGE_PERIOD_LINE } from '@/lib/aiCopy'
import {
  absDecimal,
  currentUtcMonth,
  describeActionsInScope,
  displayCostWithUnknown,
  displayRecordCost,
  displayTokenCount,
  displayTokensWithUnknown,
  displayUnknown,
  displayUsdEstimate,
  displayUsageSource,
  formatUtcMonthLabel,
  formatUtcTimestamp,
  isValidUsageMonth,
} from '@/lib/aiDisplay'
import type { AiUsageByDay, AiUsageByProviderModel, UsageTotals } from '@/types/ai'

function TotalsSummary({ totals }: { totals: UsageTotals }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div>
        <dt className="text-xs text-muted-foreground">Requests</dt>
        <dd className="text-sm font-medium text-foreground">{totals.requests}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Estimated cost</dt>
        <dd className="text-sm font-medium text-foreground">{displayCostWithUnknown(totals)}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Committed (budget)</dt>
        <dd className="text-sm font-medium text-foreground">{displayUsdEstimate(totals.committed_usd)}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Input tokens</dt>
        <dd className="text-sm font-medium text-foreground">
          {displayTokensWithUnknown(totals.input_tokens, totals.token_unknown_requests)}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Output tokens</dt>
        <dd className="text-sm font-medium text-foreground">
          {displayTokensWithUnknown(totals.output_tokens, totals.token_unknown_requests)}
        </dd>
      </div>
    </dl>
  )
}

function BudgetBar({
  committed,
  budget,
  remaining,
}: {
  committed: string
  budget: string | null
  remaining: string | null
}) {
  if (budget === null) {
    return <p className="text-sm text-muted-foreground">No budget set</p>
  }
  const committedNum = Number(committed)
  const budgetNum = Number(budget)
  const over = remaining !== null ? remaining.trim().startsWith('-') : committedNum > budgetNum
  let ratio = 0
  if (Number.isFinite(committedNum) && Number.isFinite(budgetNum)) {
    if (budgetNum > 0) ratio = Math.min(100, (committedNum / budgetNum) * 100)
    else if (committedNum > 0) ratio = 100 // a zero budget with any spend is fully used
  }
  const valueText = `${displayUsdEstimate(committed)} of ${displayUsdEstimate(budget)} committed${over ? ', over budget' : ''}`
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Committed {displayUsdEstimate(committed)}</span>
        <span>Budget {displayUsdEstimate(budget)}</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-surface2"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio)}
        aria-valuetext={valueText}
        aria-label="Budget committed"
      >
        <div
          data-over-budget={over ? 'true' : undefined}
          className={`h-full transition-all ${over ? 'bg-destructive' : 'bg-primary'}`}
          style={{ width: `${ratio}%` }}
        />
      </div>
    </div>
  )
}

function BreakdownTable({ label, keyHeader, rows }: { label: string; keyHeader: string; rows: { key: string; totals: UsageTotals }[] }) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">{label}</h4>
      <Table aria-label={label}>
        <TableHeader>
          <TableRow>
            <TableHead>{keyHeader}</TableHead>
            <TableHead>Requests</TableHead>
            <TableHead>Tokens (in / out)</TableHead>
            <TableHead>Est. cost</TableHead>
            <TableHead>Committed</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map(({ key, totals }) => (
            <TableRow key={key}>
              <TableCell className="font-mono text-xs">{key}</TableCell>
              <TableCell>{totals.requests}</TableCell>
              <TableCell className="text-xs">
                {displayTokensWithUnknown(totals.input_tokens, totals.token_unknown_requests)} /{' '}
                {displayTokensWithUnknown(totals.output_tokens, totals.token_unknown_requests)}
              </TableCell>
              <TableCell>{displayCostWithUnknown(totals)}</TableCell>
              <TableCell>{displayUsdEstimate(totals.committed_usd)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

const providerModelRows = (rows: AiUsageByProviderModel[]) =>
  rows.map((r) => ({ key: `${r.provider} / ${r.model}`, totals: r }))
const dayRows = (rows: AiUsageByDay[]) => rows.map((r) => ({ key: r.date, totals: r }))

export function AiUsagePanel() {
  // `month` is always a valid YYYY-MM; `monthInput` is what the field shows.
  const [month, setMonth] = useState(currentUtcMonth())
  const [monthInput, setMonthInput] = useState(month)
  const usage = useAiUsage(month)
  const records = useAiUsageRecords(month)
  const monthError = isValidUsageMonth(monthInput) ? undefined : 'Enter a month as YYYY-MM (2000 or later).'

  const onMonthChange = (value: string) => {
    setMonthInput(value)
    if (isValidUsageMonth(value)) setMonth(value)
  }

  const shownMonth = usage.data?.period.month ?? month
  const scope = usage.data ? ` ${describeActionsInScope(usage.data.actions_in_scope)}` : ''
  const recordItems = records.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <Card>
      <section aria-labelledby="ai-usage-title" className="space-y-4 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 id="ai-usage-title" className="text-base font-semibold text-foreground">
              AI usage
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {formatUtcMonthLabel(shownMonth)}, {AI_USAGE_PERIOD_LINE}
              {scope}
            </p>
          </div>
          <Input
            id="ai-usage-month"
            label="Month (UTC)"
            type="month"
            placeholder="YYYY-MM"
            value={monthInput}
            error={monthError}
            onChange={(e) => onMonthChange(e.target.value)}
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
            <BudgetBar
              committed={usage.data.budget.committed_usd}
              budget={usage.data.budget.monthly_budget_usd}
              remaining={usage.data.budget.remaining_usd}
            />
            {usage.data.budget.remaining_usd !== null && (
              <p
                className={
                  usage.data.budget.remaining_usd.trim().startsWith('-')
                    ? 'text-sm text-destructive'
                    : 'text-sm text-muted-foreground'
                }
              >
                {usage.data.budget.remaining_usd.trim().startsWith('-') ? (
                  <>Over budget by {displayUsdEstimate(absDecimal(usage.data.budget.remaining_usd))}</>
                ) : (
                  <>Remaining budget estimate: {displayUsdEstimate(usage.data.budget.remaining_usd)}</>
                )}
              </p>
            )}
            <TotalsSummary totals={usage.data.totals} />
            {(usage.data.totals.cost_unknown_requests > 0 || usage.data.totals.token_unknown_requests > 0) && (
              <ul className="space-y-1 text-sm text-warning-ink">
                {usage.data.totals.cost_unknown_requests > 0 && (
                  <li>
                    {usage.data.totals.cost_unknown_requests} request(s) with unknown cost are not included in the
                    estimate.
                  </li>
                )}
                {usage.data.totals.token_unknown_requests > 0 && (
                  <li>
                    {usage.data.totals.token_unknown_requests} request(s) with unknown token usage are not included in
                    the token counts.
                  </li>
                )}
              </ul>
            )}
            <BreakdownTable
              label="By provider and model"
              keyHeader="Provider / model"
              rows={providerModelRows(usage.data.by_provider_model)}
            />
            <BreakdownTable label="By day" keyHeader="Day (UTC)" rows={dayRows(usage.data.by_day)} />
          </div>
        ) : null}

        <div className="space-y-2 border-t border-border pt-4">
          <h4 className="text-sm font-medium text-foreground">Recent records</h4>
          {records.isLoading ? (
            <LoadingSpinner />
          ) : records.error ? (
            <p className="text-sm text-destructive">{aiRequestErrorMessage(records.error, "Couldn't load records.")}</p>
          ) : recordItems.length > 0 ? (
            <>
              <Table aria-label="Recent records">
                <TableHeader>
                  <TableRow>
                    <TableHead>When (UTC)</TableHead>
                    <TableHead>By</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Tokens</TableHead>
                    <TableHead>Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recordItems.map((rec) => (
                    <TableRow key={rec.id}>
                      <TableCell className="text-xs">
                        <time dateTime={rec.started_at}>{formatUtcTimestamp(rec.started_at)}</time>
                      </TableCell>
                      <TableCell className="text-xs">{displayUnknown(rec.actor_label)}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {rec.provider}/{rec.model}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            rec.status === 'succeeded' ? 'success' : rec.status === 'failed' ? 'destructive' : 'secondary'
                          }
                        >
                          {rec.status}
                          {rec.stale ? ' (stale)' : ''}
                        </Badge>
                        {rec.retry_of && <span className="block text-xs text-muted-foreground">Retry</span>}
                      </TableCell>
                      <TableCell className="text-xs">
                        {displayTokenCount(rec.input_tokens)} / {displayTokenCount(rec.output_tokens)} (
                        {displayUsageSource(rec.usage_source)})
                      </TableCell>
                      <TableCell className="text-xs">
                        {displayRecordCost(rec)}
                        {rec.error_category && (
                          <span className="block text-muted-foreground">{describeAiCategory(rec.error_category)}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {records.hasNextPage && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => records.fetchNextPage()}
                  disabled={records.isFetchingNextPage}
                >
                  {records.isFetchingNextPage ? 'Loading…' : 'Load more records'}
                </Button>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No usage records for this month.</p>
          )}
        </div>
      </section>
    </Card>
  )
}

import { useEffect, useState, type FormEvent } from 'react'
import { Warning } from '@phosphor-icons/react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { useAiUsagePolicy, useSaveAiUsagePolicy } from '@/hooks/useAiUsage'
import { useToast } from '@/contexts/ToastContext'
import { aiRequestErrorMessage } from '@/lib/aiErrors'
import { AI_GUARDRAILS_NOTICE } from '@/lib/aiCopy'
import type { AiUnpricedModelPolicy, AiUsagePolicy } from '@/types/ai'

function policyToDraft(policy: AiUsagePolicy) {
  return {
    monthly_budget_usd: policy.monthly_budget_usd ?? '',
    max_output_tokens: String(policy.max_output_tokens),
    max_concurrent_requests: String(policy.max_concurrent_requests),
    max_requests_per_minute: String(policy.max_requests_per_minute),
    unpriced_model_policy: policy.unpriced_model_policy,
  }
}

function parseDraft(draft: ReturnType<typeof policyToDraft>): Omit<AiUsagePolicy, 'updated_at' | 'guarantee'> | string {
  const max_output_tokens = Number(draft.max_output_tokens)
  const max_concurrent_requests = Number(draft.max_concurrent_requests)
  const max_requests_per_minute = Number(draft.max_requests_per_minute)
  if (!Number.isInteger(max_output_tokens) || max_output_tokens < 1 || max_output_tokens > 32000) {
    return 'Max output tokens must be between 1 and 32000.'
  }
  if (!Number.isInteger(max_concurrent_requests) || max_concurrent_requests < 1 || max_concurrent_requests > 50) {
    return 'Max concurrent requests must be between 1 and 50.'
  }
  if (!Number.isInteger(max_requests_per_minute) || max_requests_per_minute < 1 || max_requests_per_minute > 600) {
    return 'Max requests per minute must be between 1 and 600.'
  }
  const budgetTrim = draft.monthly_budget_usd.trim()
  let monthly_budget_usd: string | null = null
  if (budgetTrim !== '') {
    if (!/^\d+(\.\d{1,4})?$/.test(budgetTrim)) return 'Monthly budget must be a decimal with up to four places, or blank for none.'
    monthly_budget_usd = budgetTrim
  }
  return {
    monthly_budget_usd,
    max_output_tokens,
    max_concurrent_requests,
    max_requests_per_minute,
    unpriced_model_policy: draft.unpriced_model_policy,
  }
}

export function AiGuardrailsForm() {
  const { toast } = useToast()
  const { data, isLoading, error } = useAiUsagePolicy()
  const save = useSaveAiUsagePolicy()
  const [draft, setDraft] = useState<ReturnType<typeof policyToDraft> | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (data) setDraft(policyToDraft(data))
  }, [data])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!draft || save.isPending) return
    const parsed = parseDraft(draft)
    if (typeof parsed === 'string') {
      setFormError(parsed)
      return
    }
    setFormError(null)
    save.mutate(parsed, {
      onSuccess: () => toast('Guardrails saved', 'success'),
      onError: (err) => setFormError(aiRequestErrorMessage(err, "Couldn't save guardrails.")),
    })
  }

  const setPolicy = (unpriced_model_policy: AiUnpricedModelPolicy) => {
    setDraft((d) => (d ? { ...d, unpriced_model_policy } : d))
    setFormError(null)
  }

  return (
    <Card>
      <section aria-labelledby="ai-guardrails-title" className="space-y-4 p-5">
        <div>
          <h3 id="ai-guardrails-title" className="text-base font-semibold text-foreground">
            Spending guardrails
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">Local operational limits for billable inference tests.</p>
        </div>

        <p className="flex items-start gap-2 rounded-lg border border-warning bg-warning-soft px-3 py-2 text-sm text-warning-ink">
          <Warning size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
          {AI_GUARDRAILS_NOTICE}
        </p>

        {isLoading || !draft ? (
          <div className="flex justify-center py-6">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">{aiRequestErrorMessage(error, "Couldn't load guardrails.")}</p>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <Input
              id="ai-budget"
              label="Monthly budget (USD, blank = none)"
              value={draft.monthly_budget_usd}
              onChange={(e) => setDraft({ ...draft, monthly_budget_usd: e.target.value })}
              inputMode="decimal"
            />
            <div className="grid gap-4 sm:grid-cols-3">
              <Input
                id="ai-max-output"
                label="Max output tokens"
                type="number"
                min={1}
                max={32000}
                value={draft.max_output_tokens}
                onChange={(e) => setDraft({ ...draft, max_output_tokens: e.target.value })}
              />
              <Input
                id="ai-max-concurrent"
                label="Max concurrent requests"
                type="number"
                min={1}
                max={50}
                value={draft.max_concurrent_requests}
                onChange={(e) => setDraft({ ...draft, max_concurrent_requests: e.target.value })}
              />
              <Input
                id="ai-max-rpm"
                label="Max requests / minute"
                type="number"
                min={1}
                max={600}
                value={draft.max_requests_per_minute}
                onChange={(e) => setDraft({ ...draft, max_requests_per_minute: e.target.value })}
              />
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-foreground">Unpriced models</legend>
              <p className="text-xs text-muted-foreground">
                When no local pricing row exists, block the request or permit it with a conservative reservation.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row sm:gap-6">
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="unpriced-policy"
                    checked={draft.unpriced_model_policy === 'block'}
                    onChange={() => setPolicy('block')}
                  />
                  Block
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="unpriced-policy"
                    checked={draft.unpriced_model_policy === 'permit'}
                    onChange={() => setPolicy('permit')}
                  />
                  Permit (estimate unknown cost)
                </label>
              </div>
            </fieldset>

            {formError && (
              <p role="alert" className="text-sm text-destructive">
                {formError}
              </p>
            )}

            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save guardrails'}
            </Button>
          </form>
        )}
      </section>
    </Card>
  )
}

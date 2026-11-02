import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowSquareOut, CheckCircle, Info, Warning, WarningCircle } from '@phosphor-icons/react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useToast } from '@/contexts/ToastContext'
import { useAiInferenceTestPreview } from '@/hooks/useAiUsage'
import {
  useAiInferenceTest,
  useAiModels,
  useAiSettings,
  useCheckAiConnection,
  useClearAiDefault,
  useRefreshAiModels,
  useRemoveAiProvider,
  useSaveAiKey,
  useSetAiDefault,
} from '@/hooks/useAiSettings'
import { aiRequestErrorMessage, describeAiCategory } from '@/lib/aiErrors'
import { displayTokenCount, displayUsdEstimate, inferenceTestBlockReason } from '@/lib/aiDisplay'
import { formatRelativeTime } from '@/lib/utils'
import type { AiProvider, AiProviderStatus, AiSettings as AiSettingsData } from '@/types/ai'
import { AiGuardrailsForm } from './AiGuardrails'
import { AiPricingTable } from './AiPricing'
import { AiUsagePanel } from './AiUsage'
import { ModelPicker, ModelSourceLabel } from './ModelPicker'

/** Fixed prompt the backend sends for the inference test (shown verbatim in the confirm dialog). */
export const INFERENCE_TEST_PROMPT = 'Reply with the single word: OK'

export function AiSettings() {
  const { data, isLoading, error } = useAiSettings()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">AI providers</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Bring your own API keys. Keys are encrypted at rest and can't be viewed again after saving.
        </p>
      </div>

      <Disclosure />

      <AiGuardrailsForm />
      <AiUsagePanel />
      <AiPricingTable />

      {isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : error || !data ? (
        <p className="text-sm text-destructive">
          {aiRequestErrorMessage(error, "Couldn't load AI settings.")}
        </p>
      ) : (
        <>
          <div className="space-y-4">
            {data.providers.map((status) => (
              <ProviderCard key={status.provider} status={status} />
            ))}
          </div>
          <DefaultModelSection settings={data} />
        </>
      )}
    </div>
  )
}

function Disclosure() {
  return (
    <div className="flex gap-3 rounded-xl border border-border bg-surface2 p-4">
      <Info size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-primary" />
      <div className="space-y-1 text-sm">
        <p className="font-medium text-foreground">AI providers are external, paid services</p>
        <p className="text-muted-foreground">
          Each provider bills your account for usage and handles data under its own policies. Saving a key,
          checking a connection, or listing models never sends indicators, reports, or other data from this
          instance. Nothing is sent to a provider until a future feature asks you to.
        </p>
      </div>
    </div>
  )
}

function maskedHint(hint: string | null) {
  return hint ? `••••${hint}` : '••••'
}

function StatusLine({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  const Icon = ok ? CheckCircle : WarningCircle
  return (
    <p role="status" className={ok ? 'flex items-start gap-1.5 text-sm text-success-ink' : 'flex items-start gap-1.5 text-sm text-destructive'}>
      <Icon size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  )
}

function ProviderCard({ status }: { status: AiProviderStatus }) {
  const { toast } = useToast()
  const { provider, display_name: name, configured } = status
  const [apiKey, setApiKey] = useState('')
  const [keyError, setKeyError] = useState<string | null>(null)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const save = useSaveAiKey()
  const remove = useRemoveAiProvider()
  const check = useCheckAiConnection()
  const refresh = useRefreshAiModels()
  const inputId = `ai-key-${provider}`
  // Save and remove write the same resource; the server could apply them in either
  // order, so only one may be in flight at a time.
  const keyBusy = save.isPending || remove.isPending

  const handleSave = (e: FormEvent) => {
    e.preventDefault()
    const key = apiKey.trim()
    if (!key || keyBusy) return
    save.mutate(
      { provider, apiKey: key },
      {
        onSuccess: () => {
          setApiKey('')
          setKeyError(null)
          check.reset()
          refresh.reset()
          toast(`${name} key saved`, 'success')
        },
        onError: (err) => setKeyError(aiRequestErrorMessage(err, "Couldn't save the key.")),
        // Drop the settled mutation (its variables hold the key) from TanStack state.
        onSettled: () => save.reset(),
      },
    )
  }

  const handleRemove = () => {
    if (keyBusy) return
    remove.mutate(provider, {
      onSuccess: () => {
        setConfirmRemove(false)
        check.reset()
        refresh.reset()
        toast(`${name} key removed`, 'success')
      },
      onError: (err) => {
        setConfirmRemove(false)
        toast(aiRequestErrorMessage(err, `Couldn't remove the ${name} key.`), 'error')
      },
    })
  }

  let connection: React.ReactNode = null
  if (check.isPending) {
    connection = <p className="text-sm text-muted-foreground">Checking connection…</p>
  } else if (check.data) {
    connection = check.data.ok ? (
      <StatusLine ok>Connection OK. The key works.</StatusLine>
    ) : (
      <StatusLine ok={false}>{describeAiCategory(check.data.error?.category)}</StatusLine>
    )
  } else if (check.isError) {
    connection = <StatusLine ok={false}>{aiRequestErrorMessage(check.error, "Couldn't check the connection.")}</StatusLine>
  } else if (configured && status.last_check_status) {
    const when = status.last_checked_at ? ` (checked ${formatRelativeTime(status.last_checked_at)})` : ''
    connection =
      status.last_check_status === 'ok' ? (
        <StatusLine ok>Connection OK{when}</StatusLine>
      ) : (
        <StatusLine ok={false}>
          {describeAiCategory(status.last_check_category)}
          {when}
        </StatusLine>
      )
  } else if (configured) {
    connection = <p className="text-sm text-muted-foreground">Connection not checked yet.</p>
  }

  let refreshed: React.ReactNode = null
  if (refresh.isPending) {
    refreshed = <p className="text-sm text-muted-foreground">Refreshing models…</p>
  } else if (refresh.data) {
    const count = refresh.data.models.length
    refreshed = (
      <div className="space-y-1">
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          {count} {count === 1 ? 'model' : 'models'} available
          <ModelSourceLabel list={refresh.data} />
        </p>
        {refresh.data.error && (
          <p role="status" className="flex items-start gap-1.5 text-xs text-warning-ink">
            <Warning size={14} aria-hidden="true" className="mt-px shrink-0" />
            <span>Couldn't fetch the live model list: {describeAiCategory(refresh.data.error.category)}</span>
          </p>
        )}
      </div>
    )
  } else if (refresh.isError) {
    refreshed = <StatusLine ok={false}>{aiRequestErrorMessage(refresh.error, "Couldn't refresh models.")}</StatusLine>
  }

  return (
    <Card>
      <section aria-labelledby={`${inputId}-title`} className="space-y-4 p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 id={`${inputId}-title`} className="text-base font-semibold text-foreground">
                {name}
              </h3>
              {configured ? <Badge variant="success">Configured</Badge> : <Badge variant="secondary">Not configured</Badge>}
            </div>
            {configured ? (
              <p className="text-sm text-muted-foreground">
                Key{' '}
                <code className="rounded bg-surface2 px-1.5 py-0.5 font-mono text-xs text-foreground" aria-label="Masked API key">
                  {maskedHint(status.key_hint)}
                </code>
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">No key saved.</p>
            )}
          </div>
          <a
            href={status.setup_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            Get an API key
            <ArrowSquareOut size={14} aria-hidden="true" />
          </a>
        </div>

        <form onSubmit={handleSave} className="flex flex-col gap-2 sm:flex-row sm:items-start">
          <div className="flex-1">
            <Input
              id={inputId}
              label={configured ? `Replace ${name} API key` : `${name} API key`}
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
                if (keyError) setKeyError(null)
              }}
              placeholder={configured ? 'Paste a new key to replace the saved one' : 'Paste your API key'}
              error={keyError ?? undefined}
            />
          </div>
          <Button type="submit" className="sm:mt-7" disabled={!apiKey.trim() || keyBusy}>
            {save.isPending ? 'Saving…' : configured ? 'Replace key' : 'Save key'}
          </Button>
        </form>

        {configured && (
          <div className="space-y-3 border-t border-border pt-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => check.mutate(provider)}
                disabled={check.isPending}
                aria-describedby={`${inputId}-check-help`}
              >
                Check connection
              </Button>
              <Button variant="outline" size="sm" onClick={() => refresh.mutate(provider)} disabled={refresh.isPending}>
                Refresh models
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive sm:ml-auto"
                onClick={() => setConfirmRemove(true)}
                disabled={keyBusy}
              >
                Remove key
              </Button>
            </div>
            <p id={`${inputId}-check-help`} className="text-xs text-muted-foreground">
              Checking the connection is free: it verifies the key without running a model.
            </p>
            {connection}
            {refreshed}
          </div>
        )}
      </section>

      <Dialog open={confirmRemove} onClose={() => setConfirmRemove(false)} title={`Remove ${name} key?`}>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The saved key and cached model list for {name} will be deleted. If {name} is the default provider,
            the default model is cleared too. Nothing falls back to another provider.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setConfirmRemove(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleRemove} disabled={keyBusy}>
              {remove.isPending ? 'Removing…' : 'Remove key'}
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  )
}

function DefaultModelSection({ settings }: { settings: AiSettingsData }) {
  const { toast } = useToast()
  const configured = settings.providers.filter((p) => p.configured)
  const current = settings.default
  const nameOf = (p: AiProvider) => settings.providers.find((s) => s.provider === p)?.display_name ?? p

  const [draftProvider, setDraftProvider] = useState<AiProvider | null>(
    current?.provider ?? configured[0]?.provider ?? null,
  )
  const [draftModel, setDraftModel] = useState(current?.model ?? '')
  const [draftCustom, setDraftCustom] = useState(current?.is_custom ?? false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [testOpen, setTestOpen] = useState(false)

  const setDefault = useSetAiDefault()
  const clearDefault = useClearAiDefault()
  const inference = useAiInferenceTest()
  const preview = useAiInferenceTestPreview(draftProvider, draftModel, testOpen)

  // Save and clear write the same setting; only one may be in flight at a time.
  const defaultBusy = setDefault.isPending || clearDefault.isPending

  const configuredKey = configured.map((p) => p.provider).join(',')

  // Follow the saved default whenever it changes (saved, cleared, or provider removed).
  // Refetches that leave it unchanged don't run this, so an unsaved draft survives them.
  const prevDefault = useRef(current)
  useEffect(() => {
    const previous = prevDefault.current
    prevDefault.current = current
    if (current) {
      setDraftProvider(current.provider)
      setDraftModel(current.model)
      setDraftCustom(current.is_custom)
    } else if (previous) {
      // Cleared (possibly by another admin): drop the stale selection so it can't be
      // re-saved by accident. The provider stays; the effect below handles it if unconfigured.
      setDraftModel('')
      setDraftCustom(false)
    }
  }, [current?.provider, current?.model, current?.is_custom])

  // A draft pointing at a provider that is no longer configured is reset, never silently swapped.
  useEffect(() => {
    const available = configuredKey ? (configuredKey.split(',') as AiProvider[]) : []
    if (draftProvider && available.includes(draftProvider)) return
    const next = current?.provider ?? available[0] ?? null
    setDraftProvider(next)
    setDraftModel(current && current.provider === next ? current.model : '')
    setDraftCustom(current && current.provider === next ? current.is_custom : false)
  }, [configuredKey])

  const models = useAiModels(draftProvider, !!draftProvider)
  const loadError = models.isError ? aiRequestErrorMessage(models.error, "Couldn't load the model list.") : null

  const selectProvider = (provider: AiProvider) => {
    setDraftProvider(provider)
    const same = current?.provider === provider
    setDraftModel(same ? current!.model : '')
    setDraftCustom(same ? current!.is_custom : false)
    setSaveError(null)
    inference.reset()
  }

  const unchanged =
    !!current &&
    current.provider === draftProvider &&
    current.model === draftModel &&
    current.is_custom === draftCustom
  // Whitespace-only IDs are rejected by the API; otherwise the ID is sent byte-for-byte.
  const hasModel = draftModel.trim() !== ''

  const handleSave = () => {
    if (!draftProvider || !hasModel || defaultBusy) return
    setSaveError(null)
    setDefault.mutate(
      { provider: draftProvider, model: draftModel, is_custom: draftCustom },
      {
        onSuccess: () => toast('Default model saved', 'success'),
        onError: (err) => setSaveError(aiRequestErrorMessage(err, "Couldn't save the default model.")),
      },
    )
  }

  const handleClear = () => {
    if (defaultBusy) return
    clearDefault.mutate(undefined, {
      onSuccess: () => {
        setDraftModel('')
        setDraftCustom(false)
        toast('Default model cleared', 'success')
      },
      onError: (err) => toast(aiRequestErrorMessage(err, "Couldn't clear the default model."), 'error'),
    })
  }

  const confirmTest = () => {
    if (!draftProvider || !hasModel) return
    setTestOpen(false)
    inference.mutate({ provider: draftProvider, model: draftModel })
  }

  let testResult: React.ReactNode = null
  const tested = inference.variables
  if (inference.isPending) {
    testResult = <p className="text-sm text-muted-foreground">Sending test prompt…</p>
  } else if (inference.data && tested) {
    const usage = inference.data.usage
    testResult = inference.data.ok ? (
      <div className="space-y-1">
        <StatusLine ok>
          <code className="font-mono text-xs">{tested.model}</code> replied
          {inference.data.latency_ms != null ? ` in ${inference.data.latency_ms} ms` : ''}.
        </StatusLine>
        {usage && (
          <p className="text-xs text-muted-foreground">
            Usage: {displayTokenCount(usage.input_tokens)} in / {displayTokenCount(usage.output_tokens)} out, cost{' '}
            {displayUsdEstimate(usage.cost_usd)}
          </p>
        )}
      </div>
    ) : (
      <StatusLine ok={false}>{describeAiCategory(inference.data.error?.category)}</StatusLine>
    )
  } else if (inference.isError) {
    testResult = <StatusLine ok={false}>{aiRequestErrorMessage(inference.error, "Couldn't run the test.")}</StatusLine>
  }

  return (
    <Card>
      <section aria-labelledby="ai-default-title" className="space-y-4 p-5">
        <div>
          <h3 id="ai-default-title" className="text-base font-semibold text-foreground">
            Default model
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            The provider and model future AI features will use for this instance.
          </p>
        </div>

        <div className="rounded-lg border border-border bg-surface2 px-4 py-3 text-sm">
          {current ? (
            <p className="flex flex-wrap items-center gap-2 text-foreground">
              <span className="text-muted-foreground">Current default:</span>
              <span className="font-medium">{nameOf(current.provider)}</span>
              <code className="break-all font-mono text-xs">{current.model}</code>
              {current.is_custom && <Badge variant="secondary">Custom ID</Badge>}
            </p>
          ) : (
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">No default model.</span> AI features stay off until
              you choose one. Nothing falls back to another provider.
            </p>
          )}
        </div>

        {configured.length === 0 ? (
          <p className="text-sm text-muted-foreground">Save a provider key above to choose a default model.</p>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]">
              <Select
                id="ai-default-provider"
                label="Provider"
                value={draftProvider ?? ''}
                onChange={(e) => selectProvider(e.target.value as AiProvider)}
                options={configured.map((p) => ({ value: p.provider, label: p.display_name }))}
              />
              <ModelPicker
                list={models.data}
                isLoading={models.isLoading}
                loadError={loadError}
                value={draftModel}
                isCustom={draftCustom}
                onChange={(model, isCustom) => {
                  setDraftModel(model)
                  setDraftCustom(isCustom)
                  setSaveError(null)
                }}
              />
            </div>

            {saveError && (
              <p role="alert" className="text-sm text-destructive">
                {saveError}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={handleSave} disabled={!hasModel || unchanged || defaultBusy}>
                {setDefault.isPending ? 'Saving…' : 'Save default'}
              </Button>
              {current && (
                <Button variant="outline" onClick={handleClear} disabled={defaultBusy}>
                  Clear default
                </Button>
              )}
              <Button variant="ghost" className="sm:ml-auto" onClick={() => setTestOpen(true)} disabled={!hasModel || inference.isPending}>
                Send test prompt…
              </Button>
            </div>
            {testResult}
          </>
        )}
      </section>

      <Dialog open={testOpen} onClose={() => setTestOpen(false)} title="Send a test prompt?">
        <div className="space-y-4 text-sm">
          {preview.isLoading ? (
            <div className="flex justify-center py-4">
              <LoadingSpinner />
            </div>
          ) : preview.error ? (
            <p className="text-destructive">{aiRequestErrorMessage(preview.error, "Couldn't load preview.")}</p>
          ) : preview.data ? (
            <>
              <p className="text-muted-foreground">{preview.data.destination_note}</p>
              <p>
                Exact prompt:{' '}
                <code className="break-all font-mono text-xs text-foreground">{preview.data.content}</code>
              </p>
              <p>Max output tokens: {preview.data.max_output_tokens}</p>
              <p>
                Estimated max cost:{' '}
                {preview.data.pricing_known
                  ? displayUsdEstimate(preview.data.estimated_max_cost_usd)
                  : 'Unknown, unpriced'}
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">
              This sends one tiny fixed prompt to {draftProvider ? nameOf(draftProvider) : 'the provider'} using{' '}
              <code className="break-all font-mono text-xs text-foreground">{draftModel}</code>.
            </p>
          )}
          <p className="flex items-start gap-2 rounded-lg border border-warning bg-warning-soft px-3 py-2 text-warning-ink">
            <Warning size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
            The provider may charge for this request.
          </p>
          {preview.data && preview.data.policy_decision !== 'allowed' && (
            <p role="status" className="text-destructive">
              {inferenceTestBlockReason(preview.data.policy_decision)}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setTestOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={confirmTest}
              disabled={
                preview.isLoading ||
                !!preview.error ||
                !preview.data ||
                preview.data.policy_decision !== 'allowed'
              }
              title={
                preview.data && preview.data.policy_decision !== 'allowed'
                  ? inferenceTestBlockReason(preview.data.policy_decision) ?? undefined
                  : undefined
              }
            >
              Send test prompt
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  )
}

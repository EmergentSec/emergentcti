import { useEffect, useState } from 'react'
import { Input, controlClass } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import type { Feed, FeedCreate, FeedType, FeedUpdate } from '@/types/feed'
import {
  AUTH_CONFIG_EXAMPLES,
  AUTH_CONFIG_PLACEHOLDER,
  validateFullAuthConfig,
} from '@/lib/feedAuthValidation'
import { TlpDowngradeReasonDialog } from '@/components/common/TlpDowngradeReasonDialog'
import {
  TLP_SELECT_OPTIONS,
  formatTlpSelectValue,
  needsTlpChangeReason,
  parseTlpSelectValue,
} from '@/lib/tlp'
import { cn } from '@/lib/utils'

// ── Prop types ────────────────────────────────────────────────────────────────

interface FeedFormSharedProps {
  onCancel: () => void
  isLoading?: boolean
  /** Server validation message (e.g. HTTP 422 detail) shown inline on the form */
  submitError?: string | null
}

// Create mode: no initialValues → onSubmit receives FeedCreate
type FeedFormCreateProps = FeedFormSharedProps & {
  initialValues?: undefined
  onSubmit: (data: FeedCreate) => void
}

// Edit mode: initialValues provided → onSubmit receives FeedUpdate
type FeedFormEditProps = FeedFormSharedProps & {
  initialValues: Feed
  onSubmit: (data: FeedUpdate) => void
}

export type FeedFormProps = FeedFormCreateProps | FeedFormEditProps

// ── Constants ─────────────────────────────────────────────────────────────────

const feedTypeOptions = [
  { value: 'api', label: 'API' },
  { value: 'file', label: 'File/List' },
  { value: 'scraper', label: 'Scraper' },
]

const DEFAULT_CREATE_SCHEDULE = '0 */6 * * *'

// ── Component ─────────────────────────────────────────────────────────────────

export function FeedForm(props: FeedFormProps) {
  const { onCancel, isLoading, submitError } = props
  const isEditMode = props.initialValues != null
  const iv = isEditMode ? props.initialValues : null

  // Edit-mode derived flags (defined once, used for field gating throughout)
  const preconfigured = iv?.is_preconfigured ?? false
  const authNeedsRepair = Boolean(iv?.auth_needs_repair)
  const knownAuth = Boolean(iv?.has_auth || iv?.auth_supported)
  const showFriendlyKeyRotation =
    isEditMode && knownAuth && !authNeedsRepair

  // ── Local state — seeded from initialValues in edit mode ─────────────────
  const [name, setName] = useState(iv?.name ?? '')
  const [description, setDescription] = useState(iv?.description ?? '')
  const [feedType, setFeedType] = useState<FeedType>(iv?.feed_type ?? 'file')
  const [url, setUrl] = useState(iv?.url ?? '')
  const [scheduleCron, setScheduleCron] = useState(
    isEditMode ? (iv?.schedule_cron ?? '') : DEFAULT_CREATE_SCHEDULE,
  )
  const [defaultConfidence, setDefaultConfidence] = useState(iv?.default_confidence ?? 50)
  const [enabled, setEnabled] = useState(iv?.enabled ?? true)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [replaceFullAuth, setReplaceFullAuth] = useState(false)

  // Auth state — authConfig: JSON textarea (create mode + edit !knownAuth)
  //              apiKeyValue: friendly API key field (edit mode + knownAuth)
  const [authConfig, setAuthConfig] = useState('')
  const [apiKeyValue, setApiKeyValue] = useState('')
  const [tlpValue, setTlpValue] = useState(formatTlpSelectValue(iv?.tlp))
  const [showDowngradeDialog, setShowDowngradeDialog] = useState(false)
  const [pendingSubmit, setPendingSubmit] = useState<FeedCreate | FeedUpdate | null>(null)

  useEffect(() => {
    if (iv) setTlpValue(formatTlpSelectValue(iv.tlp))
  }, [iv?.id, iv?.tlp])

  useEffect(() => {
    if (!submitError) return
    setErrors((prev) => ({ ...prev, form: submitError }))
  }, [submitError])

  // ── Validation ────────────────────────────────────────────────────────────

  const validateAuthJson = (raw: string, feedUrlForTemplate: string): string | null => {
    if (!raw.trim()) return null
    let parsed: unknown
    try {
      parsed = JSON.parse(raw)
    } catch {
      return 'Must be valid JSON'
    }
    return validateFullAuthConfig(parsed, feedUrlForTemplate)
  }

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    // Name required in create mode and custom edit (not preconfigured edit)
    if (!isEditMode || (isEditMode && !preconfigured)) {
      if (!name.trim()) newErrors.name = 'Name is required'
    }

    // URL required in create mode and custom edit (preconfigured URL is read-only)
    if (!isEditMode || (isEditMode && !preconfigured)) {
      if (!url.trim()) newErrors.url = 'URL is required'
    }

    const urlForAuth = preconfigured && iv ? (iv.url ?? url) : url

    const shouldValidateAuthJson =
      authConfig.trim() &&
      (!isEditMode ||
        authNeedsRepair ||
        replaceFullAuth ||
        (!preconfigured && !knownAuth))

    if (shouldValidateAuthJson) {
      const authErr = validateAuthJson(authConfig, urlForAuth)
      if (authErr) newErrors.authConfig = authErr
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  const submitPayload = (data: FeedCreate | FeedUpdate, reason?: string) => {
    if (reason) {
      ;(data as FeedCreate).tlp_change_reason = reason
    }
    props.onSubmit(data as FeedCreate & FeedUpdate)
  }

  const finishSubmit = (data: FeedCreate | FeedUpdate) => {
    if (isEditMode && iv) {
      const nextTlp = (data as FeedUpdate).tlp
      if (nextTlp !== undefined && needsTlpChangeReason(iv.tlp, nextTlp ?? null)) {
        setPendingSubmit(data)
        setShowDowngradeDialog(true)
        return
      }
    }
    submitPayload(data)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})
    if (!validate()) return

    if (!isEditMode) {
      // ── Create mode ──────────────────────────────────────────────────────
      const data: FeedCreate = {
        name: name.trim(),
        feed_type: feedType,
        url: url.trim(),
        enabled,
        default_confidence: defaultConfidence,
      }
      if (description.trim()) data.description = description.trim()
      if (scheduleCron.trim()) data.schedule_cron = scheduleCron.trim()
      if (authConfig.trim()) data.auth_config = JSON.parse(authConfig)
      data.tlp = parseTlpSelectValue(tlpValue)
      finishSubmit(data)
    } else {
      // ── Edit mode — diff against initial feed values ─────────────────────
      const data: FeedUpdate = {}
      const feed = iv!

      const trimmedDesc = description.trim()
      const initialDesc = (feed.description ?? '').trim()
      if (trimmedDesc !== initialDesc) {
        data.description = trimmedDesc === '' ? null : trimmedDesc
      }

      const trimmedCron = scheduleCron.trim()
      const initialCron = (feed.schedule_cron ?? '').trim()
      if (trimmedCron !== initialCron) {
        data.schedule_cron = trimmedCron === '' ? null : trimmedCron
      }

      if (enabled !== feed.enabled) data.enabled = enabled
      if (defaultConfidence !== feed.default_confidence) {
        data.default_confidence = defaultConfidence
      }

      const nextTlp = parseTlpSelectValue(tlpValue)
      if (nextTlp !== feed.tlp) {
        data.tlp = nextTlp
      }

      if (!preconfigured) {
        const trimmedName = name.trim()
        if (trimmedName !== feed.name) data.name = trimmedName
        if (feedType !== feed.feed_type) data.feed_type = feedType
        const trimmedUrl = url.trim()
        if (trimmedUrl !== (feed.url ?? '').trim()) data.url = trimmedUrl
      }

      if (authNeedsRepair) {
        if (authConfig.trim()) {
          data.auth_config = JSON.parse(authConfig)
        }
      } else if (showFriendlyKeyRotation && replaceFullAuth) {
        if (authConfig.trim()) {
          data.auth_config = JSON.parse(authConfig)
        }
      } else if (showFriendlyKeyRotation) {
        if (apiKeyValue.trim()) {
          data.auth_config = { api_key_value: apiKeyValue.trim() }
        }
      } else if (!preconfigured && authConfig.trim()) {
        data.auth_config = JSON.parse(authConfig)
      }

      finishSubmit(data)
    }
  }

  // ── API key field placeholder (edit mode) ─────────────────────────────────
  const apiKeyPlaceholder = iv?.has_auth
    ? 'Leave blank to keep current key'
    : 'Enter API key'

  // ── Shared auth JSON textarea markup ─────────────────────────────────────
  const authJsonTextarea = (
    <div className="space-y-1.5">
      <label htmlFor="feed-auth-config" className="text-sm font-medium text-foreground">
        Auth Config (JSON, optional)
      </label>
      <textarea
        id="feed-auth-config"
        value={authConfig}
        onChange={(e) => setAuthConfig(e.target.value)}
        placeholder={AUTH_CONFIG_PLACEHOLDER}
        rows={4}
        aria-invalid={errors.authConfig ? true : undefined}
        aria-describedby={
          errors.authConfig ? 'feed-auth-config-error' : 'feed-auth-config-help'
        }
        className={cn(
          controlClass,
          'h-auto min-h-20 resize-y py-2 font-mono text-sm',
          errors.authConfig &&
            'border-destructive focus-visible:border-destructive focus-visible:ring-destructive',
        )}
      />
      <p id="feed-auth-config-help" className="whitespace-pre-line text-xs text-muted-foreground">
        {AUTH_CONFIG_EXAMPLES}
      </p>
      {errors.authConfig && (
        <p id="feed-auth-config-error" className="text-xs text-destructive">
          {errors.authConfig}
        </p>
      )}
    </div>
  )

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
    <form onSubmit={handleSubmit} className="space-y-4">
      {errors.form && (
        <p role="alert" className="rounded-lg border border-destructive bg-destructive-soft px-3 py-2 text-sm text-destructive-ink">
          {errors.form}
        </p>
      )}

      {isEditMode && authNeedsRepair && (
        <p
          role="status"
          className="rounded-lg border border-warning bg-warning-soft px-3 py-2 text-sm text-warning-ink"
        >
          Stored authentication for this feed is invalid or outdated. Enter a full auth
          configuration below to repair it (secrets are never shown).
        </p>
      )}

      {/* Feed Name: read-only text for preconfigured edit; editable input otherwise */}
      {isEditMode && preconfigured ? (
        <div className="space-y-1.5">
          <span className="text-sm font-medium text-foreground">Feed Name</span>
          <p className="text-sm text-foreground">{iv!.name}</p>
        </div>
      ) : (
        <Input
          label="Feed Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My Custom Feed"
          error={errors.name}
        />
      )}

      <Input
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Optional description"
      />

      {/* Feed Type: read-only text for preconfigured edit; select otherwise */}
      {isEditMode && preconfigured ? (
        <div className="space-y-1.5">
          <span className="text-sm font-medium text-foreground">Feed Type</span>
          <p className="text-sm text-foreground">{iv!.feed_type}</p>
        </div>
      ) : (
        <Select
          label="Feed Type"
          options={feedTypeOptions}
          value={feedType}
          onChange={(e) => setFeedType(e.target.value as FeedType)}
        />
      )}

      {/* URL: disabled input for preconfigured edit; editable input otherwise */}
      {isEditMode && preconfigured ? (
        <Input
          label="URL"
          value={url}
          disabled
        />
      ) : (
        <Input
          label="URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/feed.txt"
          error={errors.url}
        />
      )}

      <Input
        label="Schedule (cron)"
        value={scheduleCron}
        onChange={(e) => setScheduleCron(e.target.value)}
        placeholder={isEditMode ? 'Leave empty for no schedule' : DEFAULT_CREATE_SCHEDULE}
      />

      <div className="space-y-1.5">
        <label htmlFor="feed-confidence" className="text-sm font-medium text-foreground">
          Default Confidence: {defaultConfidence}
        </label>
        <input
          id="feed-confidence"
          type="range"
          min="0"
          max="100"
          step="5"
          value={defaultConfidence}
          onChange={(e) => setDefaultConfidence(parseInt(e.target.value))}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-xl bg-surface3 accent-primary"
        />
      </div>

      <Select
        label="TLP marking"
        options={TLP_SELECT_OPTIONS}
        value={tlpValue}
        onChange={(e) => setTlpValue(e.target.value)}
      />
      <p className="text-xs text-muted-foreground">
        Applies to every observable this feed contributes. Unspecified means no sharing policy is
        recorded yet.
      </p>

      {/* Auth section */}
      {isEditMode ? (
        authNeedsRepair ? (
          authJsonTextarea
        ) : showFriendlyKeyRotation ? (
          <div className="space-y-3">
            <Input
              label="API Key"
              type="password"
              value={apiKeyValue}
              onChange={(e) => setApiKeyValue(e.target.value)}
              placeholder={apiKeyPlaceholder}
            />
            <Toggle
              checked={replaceFullAuth}
              onChange={setReplaceFullAuth}
              label="Replace full auth configuration"
            />
            {replaceFullAuth ? authJsonTextarea : null}
          </div>
        ) : (
          !preconfigured ? authJsonTextarea : null
        )
      ) : (
        authJsonTextarea
      )}

      <Toggle checked={enabled} onChange={setEnabled} label="Enabled" />

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isEditMode
            ? isLoading
              ? 'Saving...'
              : 'Save Changes'
            : isLoading
              ? 'Creating...'
              : 'Create Feed'}
        </Button>
      </div>
    </form>
      <TlpDowngradeReasonDialog
        open={showDowngradeDialog}
        onClose={() => {
          setShowDowngradeDialog(false)
          setPendingSubmit(null)
        }}
        isLoading={isLoading}
        onConfirm={(reason) => {
          if (pendingSubmit) submitPayload(pendingSubmit, reason)
          setShowDowngradeDialog(false)
          setPendingSubmit(null)
        }}
      />
    </>
  )
}

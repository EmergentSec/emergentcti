import { useState } from 'react'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import type { Feed, FeedCreate, FeedType, FeedUpdate } from '@/types/feed'

// ── Prop types ────────────────────────────────────────────────────────────────

interface FeedFormSharedProps {
  onCancel: () => void
  isLoading?: boolean
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

// ── Component ─────────────────────────────────────────────────────────────────

export function FeedForm(props: FeedFormProps) {
  const { onSubmit, onCancel, isLoading } = props
  const isEditMode = props.initialValues != null
  const iv = isEditMode ? props.initialValues : null

  // Edit-mode derived flags (defined once, used for field gating throughout)
  const preconfigured = iv?.is_preconfigured ?? false
  const knownAuth = Boolean(iv?.has_auth || iv?.auth_supported)

  // ── Local state — seeded from initialValues in edit mode ─────────────────
  const [name, setName] = useState(iv?.name ?? '')
  const [description, setDescription] = useState(iv?.description ?? '')
  const [feedType, setFeedType] = useState<FeedType>(iv?.feed_type ?? 'file')
  const [url, setUrl] = useState(iv?.url ?? '')
  const [scheduleCron, setScheduleCron] = useState(iv?.schedule_cron ?? '0 */6 * * *')
  const [defaultConfidence, setDefaultConfidence] = useState(iv?.default_confidence ?? 50)
  const [enabled, setEnabled] = useState(iv?.enabled ?? true)
  const [errors, setErrors] = useState<Record<string, string>>({})

  // Auth state — authConfig: JSON textarea (create mode + edit !knownAuth)
  //              apiKeyValue: friendly API key field (edit mode + knownAuth)
  const [authConfig, setAuthConfig] = useState('')
  const [apiKeyValue, setApiKeyValue] = useState('')

  // ── Validation ────────────────────────────────────────────────────────────

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

    // JSON auth config validation whenever the textarea is shown and non-empty
    if (authConfig.trim()) {
      try {
        JSON.parse(authConfig)
      } catch {
        newErrors.authConfig = 'Must be valid JSON'
      }
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
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
      onSubmit(data)
    } else {
      // ── Edit mode ─────────────────────────────────────────────────────────
      const data: FeedUpdate = {
        enabled,
        default_confidence: defaultConfidence,
      }
      const trimmedDesc = description.trim()
      data.description = trimmedDesc || undefined
      if (scheduleCron.trim()) data.schedule_cron = scheduleCron.trim()

      // Structural fields: only send for custom (non-preconfigured) feeds
      if (!preconfigured) {
        data.name = name.trim() || undefined
        data.feed_type = feedType
        data.url = url.trim() || undefined
      }

      // Auth: friendly API key field when knownAuth; JSON textarea otherwise
      if (knownAuth) {
        if (apiKeyValue.trim()) {
          data.auth_config = { api_key_value: apiKeyValue.trim() }
        }
      } else {
        if (authConfig.trim()) {
          data.auth_config = JSON.parse(authConfig)
        }
      }

      ;(onSubmit as (data: FeedUpdate) => void)(data)
    }
  }

  // ── API key field placeholder (edit mode) ─────────────────────────────────
  const apiKeyPlaceholder = iv?.has_auth
    ? 'Leave blank to keep current key'
    : 'Enter API key'

  // ── Shared auth JSON textarea markup ─────────────────────────────────────
  const authJsonTextarea = (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-foreground">
        Auth Config (JSON, optional)
      </label>
      <textarea
        value={authConfig}
        onChange={(e) => setAuthConfig(e.target.value)}
        placeholder='{"api_key": "your-key-here"}'
        rows={3}
        className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground font-mono placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {errors.authConfig && (
        <p className="text-xs text-destructive">{errors.authConfig}</p>
      )}
    </div>
  )

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <form onSubmit={handleSubmit} className="space-y-4">

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
        value={description as string}
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
          value={url as string}
          disabled
        />
      ) : (
        <Input
          label="URL"
          value={url as string}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/feed.txt"
          error={errors.url}
        />
      )}

      <Input
        label="Schedule (cron)"
        value={scheduleCron as string}
        onChange={(e) => setScheduleCron(e.target.value)}
        placeholder="0 */6 * * *"
      />

      <div className="space-y-1.5">
        <label className="text-sm font-medium text-foreground">
          Default Confidence: {defaultConfidence}
        </label>
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={defaultConfidence}
          onChange={(e) => setDefaultConfidence(parseInt(e.target.value))}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-muted accent-primary"
        />
      </div>

      {/* Auth section */}
      {isEditMode ? (
        // Edit mode: friendly API key when knownAuth (has_auth || auth_supported);
        // JSON textarea when !knownAuth (lets a custom feed set or rotate raw auth)
        knownAuth ? (
          <Input
            label="API Key"
            type="password"
            value={apiKeyValue}
            onChange={(e) => setApiKeyValue(e.target.value)}
            placeholder={apiKeyPlaceholder}
          />
        ) : (
          authJsonTextarea
        )
      ) : (
        // Create mode: raw JSON textarea (unchanged behaviour)
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
  )
}

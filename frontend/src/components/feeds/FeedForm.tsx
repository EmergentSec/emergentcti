import { useState } from 'react'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import type { FeedCreate, FeedType } from '@/types/feed'

interface FeedFormProps {
  onSubmit: (data: FeedCreate) => void
  onCancel: () => void
  isLoading?: boolean
}

const feedTypeOptions = [
  { value: 'api', label: 'API' },
  { value: 'file', label: 'File/List' },
  { value: 'scraper', label: 'Scraper' },
]

export function FeedForm({ onSubmit, onCancel, isLoading }: FeedFormProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [feedType, setFeedType] = useState<FeedType>('file')
  const [url, setUrl] = useState('')
  const [scheduleCron, setScheduleCron] = useState('0 */6 * * *')
  const [defaultConfidence, setDefaultConfidence] = useState(50)
  const [authConfig, setAuthConfig] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}
    if (!name.trim()) newErrors.name = 'Name is required'
    if (!url.trim()) newErrors.url = 'URL is required'
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

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
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Feed Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="My Custom Feed"
        error={errors.name}
      />

      <Input
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Optional description"
      />

      <Select
        label="Feed Type"
        options={feedTypeOptions}
        value={feedType}
        onChange={(e) => setFeedType(e.target.value as FeedType)}
      />

      <Input
        label="URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://example.com/feed.txt"
        error={errors.url}
      />

      <Input
        label="Schedule (cron)"
        value={scheduleCron}
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

      <Toggle checked={enabled} onChange={setEnabled} label="Enabled" />

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Creating...' : 'Create Feed'}
        </Button>
      </div>
    </form>
  )
}

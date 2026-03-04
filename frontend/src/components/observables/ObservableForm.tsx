import { useState } from 'react'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'
import type { ObservableCreate, ObservableType } from '@/types/observable'

interface ObservableFormProps {
  onSubmit: (data: ObservableCreate) => void
  onCancel: () => void
  isLoading?: boolean
}

const typeOptions = [
  { value: 'ip-addr', label: 'IP Address' },
  { value: 'domain-name', label: 'Domain' },
  { value: 'url', label: 'URL' },
  { value: 'file-hash', label: 'File Hash' },
  { value: 'email-addr', label: 'Email' },
  { value: 'command-line', label: 'Command Line' },
]

export function ObservableForm({ onSubmit, onCancel, isLoading }: ObservableFormProps) {
  const [type, setType] = useState<ObservableType>('ip-addr')
  const [value, setValue] = useState('')
  const [confidenceScore, setConfidenceScore] = useState(75)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}
    if (!value.trim()) newErrors.value = 'Value is required'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    onSubmit({
      type,
      value: value.trim(),
      confidence_score: confidenceScore,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Select
        label="Type"
        options={typeOptions}
        value={type}
        onChange={(e) => setType(e.target.value as ObservableType)}
      />

      <Input
        label="Value"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="e.g. 192.168.1.1"
        error={errors.value}
      />

      <div className="space-y-1.5">
        <label className="text-sm font-medium text-foreground">
          Confidence Score: {confidenceScore}
        </label>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={confidenceScore}
            onChange={(e) => setConfidenceScore(parseInt(e.target.value))}
            className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-muted accent-primary"
          />
          <span className="min-w-[2rem] text-right text-xs tabular-nums text-muted-foreground">
            {confidenceScore}
          </span>
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Adding...' : 'Add Observable'}
        </Button>
      </div>
    </form>
  )
}

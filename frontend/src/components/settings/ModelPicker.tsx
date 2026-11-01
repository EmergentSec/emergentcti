import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { CaretUpDown, Check, MagnifyingGlass, PencilSimple, Warning } from '@phosphor-icons/react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { controlClass } from '@/components/ui/Input'
import { describeAiCategory } from '@/lib/aiErrors'
import { cn, formatDate, formatRelativeTime } from '@/lib/utils'
import type { AiModel, AiModelList } from '@/types/ai'

export interface ModelPickerProps {
  /** Current discovery result for the selected provider. */
  list: AiModelList | undefined
  isLoading?: boolean
  /** Message when the model list request itself failed. */
  loadError?: string | null
  value: string
  isCustom: boolean
  /** Model IDs are passed through exactly as chosen or typed: no trimming or case changes. */
  onChange: (model: string, isCustom: boolean) => void
  disabled?: boolean
  label?: string
}

const SOURCE_FALLBACK_LABEL = 'Built-in list (may be out of date)'

/** Where the model list came from: Live / Cached <time> / Built-in list. */
export function ModelSourceLabel({ list }: { list: AiModelList }) {
  if (list.source === 'live') return <Badge variant="success">Live</Badge>
  if (list.source === 'cache') {
    return (
      <Badge variant="secondary" title={list.fetched_at ? formatDate(list.fetched_at) : undefined}>
        Cached {list.fetched_at ? formatRelativeTime(list.fetched_at) : ''}
      </Badge>
    )
  }
  return <Badge variant="warning">{SOURCE_FALLBACK_LABEL}</Badge>
}

function matches(model: AiModel, q: string) {
  return model.name.toLowerCase().includes(q) || model.id.toLowerCase().includes(q)
}

const CUSTOM = '__custom__'

export function ModelPicker({
  list,
  isLoading = false,
  loadError = null,
  value,
  isCustom,
  onChange,
  disabled = false,
  label = 'Model',
}: ModelPickerProps) {
  const baseId = useId()
  const labelId = `${baseId}-label`
  const valueId = `${baseId}-value`
  const listboxId = `${baseId}-listbox`
  const customInputId = `${baseId}-custom`

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const focusCustomRef = useRef(false)
  const customInputRef = useRef<HTMLInputElement>(null)

  const models = useMemo(() => list?.models ?? [], [list])
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? models.filter((m) => matches(m, q)) : models
  }, [models, query])
  // The custom-ID entry is always last and always available.
  const options = useMemo(() => [...filtered.map((m) => m.id), CUSTOM], [filtered])
  const selected = !isCustom ? models.find((m) => m.id === value) : undefined

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  useEffect(() => {
    if (!open) return
    const el = listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)
    el?.scrollIntoView?.({ block: 'nearest' })
  }, [active, open])

  useEffect(() => {
    if (isCustom && focusCustomRef.current) {
      focusCustomRef.current = false
      customInputRef.current?.focus()
    }
  }, [isCustom])

  const openPanel = () => {
    if (disabled) return
    setQuery('')
    const idx = models.findIndex((m) => m.id === value)
    setActive(idx >= 0 ? idx : 0)
    setOpen(true)
  }

  const close = (refocus: boolean) => {
    setOpen(false)
    if (refocus) triggerRef.current?.focus()
  }

  const choose = (option: string) => {
    if (option === CUSTOM) {
      // Seed the custom field with what the user typed (exactly), or the current value.
      focusCustomRef.current = true
      onChange(query !== '' ? query : value, true)
      setOpen(false)
      return
    }
    onChange(option, false)
    close(true)
  }

  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActive((i) => Math.min(i + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((i) => Math.max(i - 1, 0))
        break
      case 'Home':
        e.preventDefault()
        setActive(0)
        break
      case 'End':
        e.preventDefault()
        setActive(options.length - 1)
        break
      case 'Enter':
        e.preventDefault()
        if (options[active] !== undefined) choose(options[active])
        break
      case 'Escape':
        e.preventDefault()
        e.stopPropagation()
        close(true)
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  const backToList = () => {
    // Keep the typed ID if it happens to be a listed model; otherwise start fresh.
    onChange(models.some((m) => m.id === value) ? value : '', false)
  }

  const fallbackNote =
    list?.source === 'cache' ? 'Showing the last cached list.' : list ? 'Showing the built-in list.' : ''

  return (
    <div ref={rootRef} className="space-y-1.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {isCustom ? (
          <label htmlFor={customInputId} id={labelId} className="block text-sm font-medium text-foreground">
            Custom model ID
          </label>
        ) : (
          <span id={labelId} className="block text-sm font-medium text-foreground">
            {label}
          </span>
        )}
        {list && <ModelSourceLabel list={list} />}
      </div>

      {isCustom ? (
        <div className="space-y-1.5">
          <input
            ref={customInputRef}
            id={customInputId}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value, true)}
            disabled={disabled}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            placeholder="exact-provider-model-id"
            className={cn(controlClass, 'font-mono')}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              Sent exactly as typed, including spaces and capitalization.
            </p>
            <Button type="button" variant="ghost" size="sm" onClick={backToList} disabled={disabled}>
              Choose from list
            </Button>
          </div>
        </div>
      ) : (
        <div className="relative">
          <button
            ref={triggerRef}
            type="button"
            disabled={disabled}
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-labelledby={`${labelId} ${valueId}`}
            onClick={() => (open ? close(false) : openPanel())}
            onKeyDown={(e) => {
              if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
                e.preventDefault()
                openPanel()
              }
            }}
            className={cn(controlClass, 'h-auto min-h-9 items-center justify-between gap-2 py-1.5 text-left')}
          >
            <span id={valueId} className="min-w-0 flex-1">
              {value ? (
                <span className="flex min-w-0 flex-col">
                  {selected && selected.name !== selected.id && (
                    <span className="truncate text-sm text-foreground">{selected.name}</span>
                  )}
                  <span className="truncate font-mono text-xs text-muted-foreground">{value}</span>
                </span>
              ) : (
                <span className="text-text3">{isLoading ? 'Loading models…' : 'Select a model'}</span>
              )}
            </span>
            <CaretUpDown size={14} aria-hidden="true" className="shrink-0 text-muted-foreground" />
          </button>

          {open && (
            <div className="absolute left-0 right-0 z-40 mt-1 overflow-hidden rounded-lg border border-border bg-popover text-foreground shadow-lg">
              <div className="flex items-center gap-2 border-b border-border px-3">
                <MagnifyingGlass size={14} aria-hidden="true" className="shrink-0 text-muted-foreground" />
                <input
                  autoFocus
                  role="combobox"
                  aria-label="Search models by name or ID"
                  aria-expanded="true"
                  aria-controls={listboxId}
                  aria-autocomplete="list"
                  aria-activedescendant={`${baseId}-opt-${active}`}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value)
                    setActive(0)
                  }}
                  onKeyDown={onSearchKey}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="Search by name or ID"
                  className="h-9 w-full bg-transparent text-sm text-foreground placeholder:text-text3 focus:outline-none"
                />
              </div>
              <ul ref={listRef} id={listboxId} role="listbox" aria-label="Models" className="max-h-72 overflow-y-auto p-1">
                {filtered.length === 0 && (
                  <li role="presentation" className="px-3 py-2 text-sm text-muted-foreground">
                    {models.length === 0 ? 'No models listed.' : 'No models match your search.'}
                  </li>
                )}
                {options.map((opt, i) => {
                  const isActive = i === active
                  if (opt === CUSTOM) {
                    return (
                      <li
                        key={CUSTOM}
                        id={`${baseId}-opt-${i}`}
                        data-index={i}
                        role="option"
                        aria-selected={false}
                        onMouseDown={(e) => e.preventDefault()}
                        onMouseEnter={() => setActive(i)}
                        onClick={() => choose(CUSTOM)}
                        className={cn(
                          'mt-1 flex cursor-pointer items-start gap-2 rounded-md border-t border-border px-3 py-2 text-sm',
                          isActive && 'bg-hover',
                        )}
                      >
                        <PencilSimple size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-muted-foreground" />
                        <span className="flex min-w-0 flex-col">
                          <span className="font-medium">Use custom model ID…</span>
                          {query !== '' && (
                            <span className="truncate font-mono text-xs text-muted-foreground">{query}</span>
                          )}
                        </span>
                      </li>
                    )
                  }
                  const model = filtered[i]
                  const isSelected = model.id === value
                  return (
                    <li
                      key={model.id}
                      id={`${baseId}-opt-${i}`}
                      data-index={i}
                      role="option"
                      aria-selected={isSelected}
                      onMouseDown={(e) => e.preventDefault()}
                      onMouseEnter={() => setActive(i)}
                      onClick={() => choose(model.id)}
                      className={cn(
                        'flex cursor-pointer items-start gap-2 rounded-md px-3 py-2 text-sm',
                        isActive && 'bg-hover',
                      )}
                    >
                      <Check
                        size={14}
                        aria-hidden="true"
                        className={cn('mt-0.5 shrink-0 text-primary', !isSelected && 'invisible')}
                      />
                      <span className="flex min-w-0 flex-col">
                        {model.name !== model.id && <span className="truncate">{model.name}</span>}
                        <span className="truncate font-mono text-xs text-muted-foreground">{model.id}</span>
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </div>
      )}

      {list?.error && (
        <p role="status" className="flex items-start gap-1.5 text-xs text-warning-ink">
          <Warning size={14} aria-hidden="true" className="mt-px shrink-0" />
          <span>
            Couldn't fetch the live model list: {describeAiCategory(list.error.category)} {fallbackNote} You can
            still enter a custom model ID.
          </span>
        </p>
      )}
      {loadError && (
        <p role="status" className="flex items-start gap-1.5 text-xs text-destructive">
          <Warning size={14} aria-hidden="true" className="mt-px shrink-0" />
          <span>{loadError} You can still enter a custom model ID.</span>
        </p>
      )}
    </div>
  )
}

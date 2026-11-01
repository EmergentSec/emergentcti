import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { ModelPicker } from './ModelPicker'
import { AI_ERROR_MESSAGES } from '@/lib/aiErrors'
import type { AiModelList } from '@/types/ai'

afterEach(cleanup)

function makeList(overrides: Partial<AiModelList> = {}): AiModelList {
  return {
    provider: 'anthropic',
    source: 'live',
    fetched_at: new Date().toISOString(),
    error: null,
    models: [
      { id: 'claude-alpha-20260101', name: 'Claude Alpha' },
      { id: 'claude-beta-20260201', name: 'Claude Beta' },
      { id: 'plain-id-model', name: 'plain-id-model' },
    ],
    ...overrides,
  }
}

function openPicker() {
  fireEvent.click(screen.getByRole('button', { name: /Model/ }))
  return screen.getByRole('combobox', { name: /Search models/ })
}

function optionTexts() {
  return screen.getAllByRole('option').map((o) => o.textContent)
}

/** Stateful wrapper so custom-mode switching behaves as it does in the app. */
function Controlled({ list, onChange }: { list: AiModelList; onChange: (m: string, c: boolean) => void }) {
  const [value, setValue] = useState('')
  const [isCustom, setIsCustom] = useState(false)
  return (
    <ModelPicker
      list={list}
      value={value}
      isCustom={isCustom}
      onChange={(m, c) => {
        setValue(m)
        setIsCustom(c)
        onChange(m, c)
      }}
    />
  )
}

describe('ModelPicker', () => {
  it('shows friendly name with the exact ID, and the custom option', () => {
    render(<ModelPicker list={makeList()} value="" isCustom={false} onChange={vi.fn()} />)
    openPicker()
    expect(screen.getByText('Claude Alpha')).toBeTruthy()
    expect(screen.getByText('claude-alpha-20260101').className).toMatch(/font-mono/)
    expect(screen.getByRole('option', { name: /Use custom model ID…/ })).toBeTruthy()
  })

  it('filters by friendly name', () => {
    render(<ModelPicker list={makeList()} value="" isCustom={false} onChange={vi.fn()} />)
    fireEvent.change(openPicker(), { target: { value: 'beta' } })
    const texts = optionTexts()
    expect(texts).toHaveLength(2)
    expect(texts[0]).toContain('claude-beta-20260201')
    expect(texts[1]).toContain('Use custom model ID…')
  })

  it('filters by model ID', () => {
    render(<ModelPicker list={makeList()} value="" isCustom={false} onChange={vi.fn()} />)
    fireEvent.change(openPicker(), { target: { value: '20260101' } })
    const texts = optionTexts()
    expect(texts).toHaveLength(2)
    expect(texts[0]).toContain('Claude Alpha')
  })

  it('selects a listed model by click and by keyboard', () => {
    const onChange = vi.fn()
    render(<ModelPicker list={makeList()} value="" isCustom={false} onChange={onChange} />)
    openPicker()
    fireEvent.click(screen.getByRole('option', { name: /Claude Beta/ }))
    expect(onChange).toHaveBeenLastCalledWith('claude-beta-20260201', false)

    const search = openPicker()
    fireEvent.keyDown(search, { key: 'ArrowDown' })
    fireEvent.keyDown(search, { key: 'Enter' })
    expect(onChange).toHaveBeenLastCalledWith('claude-beta-20260201', false)
  })

  it('switches to custom entry seeded with the exact search text', () => {
    const onChange = vi.fn()
    render(<Controlled list={makeList()} onChange={onChange} />)
    fireEvent.change(openPicker(), { target: { value: 'My-Model V2' } })
    fireEvent.click(screen.getByRole('option', { name: /Use custom model ID…/ }))
    expect(onChange).toHaveBeenLastCalledWith('My-Model V2', true)
    const input = screen.getByLabelText('Custom model ID') as HTMLInputElement
    expect(input.value).toBe('My-Model V2')
  })

  it('preserves custom input exactly, including spaces and case', () => {
    const onChange = vi.fn()
    render(<ModelPicker list={makeList()} value="" isCustom onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Custom model ID'), { target: { value: '  Acme/My-Model V2 ' } })
    expect(onChange).toHaveBeenLastCalledWith('  Acme/My-Model V2 ', true)
  })

  it('labels each model source', () => {
    const { rerender } = render(<ModelPicker list={makeList()} value="" isCustom={false} onChange={vi.fn()} />)
    expect(screen.getByText('Live')).toBeTruthy()

    const fiveMinAgo = new Date(Date.now() - 5 * 60_000).toISOString()
    rerender(
      <ModelPicker list={makeList({ source: 'cache', fetched_at: fiveMinAgo })} value="" isCustom={false} onChange={vi.fn()} />,
    )
    expect(screen.getByText('Cached 5m ago')).toBeTruthy()

    rerender(
      <ModelPicker list={makeList({ source: 'fallback', fetched_at: null })} value="" isCustom={false} onChange={vi.fn()} />,
    )
    expect(screen.getByText('Built-in list (may be out of date)')).toBeTruthy()
  })

  it('shows a discovery error inline without clearing the selection or blocking custom entry', () => {
    const onChange = vi.fn()
    const list = makeList({
      source: 'cache',
      error: { category: 'rate_limited', message: 'raw provider text' },
    })
    render(<ModelPicker list={list} value="claude-alpha-20260101" isCustom={false} onChange={onChange} />)

    expect(screen.getByText(new RegExp(AI_ERROR_MESSAGES.rate_limited.replace(/[.]/g, '\\.')))).toBeTruthy()
    expect(screen.queryByText(/raw provider text/)).toBeNull()
    expect(screen.getByRole('button', { name: /claude-alpha-20260101/ })).toBeTruthy()
    expect(onChange).not.toHaveBeenCalled()

    openPicker()
    fireEvent.click(screen.getByRole('option', { name: /Use custom model ID…/ }))
    expect(onChange).toHaveBeenCalledWith('claude-alpha-20260101', true)
  })

  it('keeps an unlisted saved model visible and still offers custom entry when the list failed to load', () => {
    const onChange = vi.fn()
    render(
      <ModelPicker list={undefined} loadError="Could not load." value="saved-model" isCustom={false} onChange={onChange} />,
    )
    expect(screen.getByText(/Could not load\. You can still enter a custom model ID\./)).toBeTruthy()
    expect(screen.getByRole('button', { name: /saved-model/ })).toBeTruthy()
    openPicker()
    expect(screen.getByText('No models listed.')).toBeTruthy()
    expect(screen.getByRole('option', { name: /Use custom model ID…/ })).toBeTruthy()
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import {
  OUTBOUND_EXPIRED_REASON,
  OUTBOUND_NOTHING_INCLUDED_REASON,
  OutboundPreviewDialog,
} from './OutboundPreviewDialog'
import { outboundPreview } from '@/test/fixtures/ai'

const preview = outboundPreview()

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function confirmButton() {
  return within(screen.getByRole('dialog', { name: 'Review outbound content' })).getByRole('button', {
    name: 'Send to provider',
  }) as HTMLButtonElement
}

describe('OutboundPreviewDialog', () => {
  it('lists included/excluded items, redactions, content, and requires explicit confirm', () => {
    const onConfirm = vi.fn()
    render(<OutboundPreviewDialog open preview={preview} onClose={() => {}} onConfirm={onConfirm} />)
    const dialog = screen.getByRole('dialog', { name: 'Review outbound content' })
    expect(within(dialog).getByText('Included')).toBeTruthy()
    expect(within(dialog).getByText('TLP restricted')).toBeTruthy()
    expect(within(dialog).getByText('2 redaction(s)')).toBeTruthy()
    // Backend TLP markings are lowercase.
    expect(within(dialog).getByText('TLP: green')).toBeTruthy()
    expect(within(dialog).getByText('TLP: red')).toBeTruthy()
    expect(within(dialog).getByText(/UNTRUSTED DATA BLOCK/)).toBeTruthy()
    fireEvent.click(confirmButton())
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('shows provider and character count; content is keyboard-scrollable (L4)', () => {
    render(<OutboundPreviewDialog open preview={preview} onClose={() => {}} onConfirm={() => {}} />)
    const dialog = screen.getByRole('dialog', { name: 'Review outbound content' })
    expect(within(dialog).getByText('anthropic')).toBeTruthy()
    expect(within(dialog).getByText('(31 characters)')).toBeTruthy()
    const pre = within(dialog).getByLabelText('Outbound content')
    expect(pre.tagName).toBe('PRE')
    expect(pre.getAttribute('tabindex')).toBe('0')
  })

  it('disables confirm with the caller reason', () => {
    render(
      <OutboundPreviewDialog
        open
        preview={preview}
        onClose={() => {}}
        onConfirm={() => {}}
        confirmDisabled
        confirmDisabledReason="Sharing is off"
      />,
    )
    expect(confirmButton().disabled).toBe(true)
    expect(screen.getByText('Sharing is off')).toBeTruthy()
  })

  it('disables confirm once the preview expires (L4)', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-02T12:00:00Z'))
    const onConfirm = vi.fn()
    render(
      <OutboundPreviewDialog
        open
        preview={outboundPreview({ expires_at: '2026-11-02T12:10:00Z' })}
        onClose={() => {}}
        onConfirm={onConfirm}
      />,
    )
    expect(confirmButton().disabled).toBe(false)
    act(() => {
      vi.advanceTimersByTime(10 * 60 * 1000)
    })
    expect(confirmButton().disabled).toBe(true)
    expect(screen.getByText(OUTBOUND_EXPIRED_REASON)).toBeTruthy()
    fireEvent.click(confirmButton())
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('disables confirm when no items are included (L4)', () => {
    const base = outboundPreview()
    render(
      <OutboundPreviewDialog
        open
        preview={outboundPreview({ items: base.items.map((i) => ({ ...i, included: false, excluded_reason: 'not_visible' })) })}
        onClose={() => {}}
        onConfirm={() => {}}
      />,
    )
    expect(confirmButton().disabled).toBe(true)
    expect(screen.getByText(OUTBOUND_NOTHING_INCLUDED_REASON)).toBeTruthy()
  })
})

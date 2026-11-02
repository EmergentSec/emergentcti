import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { OutboundPreviewDialog } from './OutboundPreviewDialog'
import type { OutboundPreview } from '@/types/ai'

const preview: OutboundPreview = {
  provider: 'anthropic',
  model: 'claude-test',
  destination_note: 'Sent to Anthropic (api.anthropic.com)',
  items: [
    {
      type: 'report',
      id: 'r-1',
      label: 'Weekly summary',
      tlp: 'GREEN',
      included: true,
      excluded_reason: null,
      redactions: 2,
    },
    {
      type: 'observable',
      id: 'o-1',
      label: '1.2.3.4',
      tlp: 'RED',
      included: false,
      excluded_reason: 'tlp_restricted',
      redactions: 0,
    },
  ],
  content: 'UNTRUSTED DATA BLOCK\n[REDACTED]',
  content_chars: 30,
  digest: 'abc',
  expires_at: '2026-11-02T12:00:00Z',
}

afterEach(() => cleanup())

describe('OutboundPreviewDialog', () => {
  it('lists included/excluded items, redactions, content, and requires explicit confirm', () => {
    const onConfirm = vi.fn()
    render(
      <OutboundPreviewDialog open preview={preview} onClose={() => {}} onConfirm={onConfirm} />,
    )
    const dialog = screen.getByRole('dialog', { name: 'Review outbound content' })
    expect(within(dialog).getByText('Included')).toBeTruthy()
    expect(within(dialog).getByText('TLP restricted')).toBeTruthy()
    expect(within(dialog).getByText('2 redaction(s)')).toBeTruthy()
    expect(within(dialog).getByText(/UNTRUSTED DATA BLOCK/)).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Send to provider' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('disables confirm with reason', () => {
    render(
      <OutboundPreviewDialog
        open
        preview={preview}
        onClose={() => {}}
        onConfirm={() => {}}
        confirmDisabled
        confirmDisabledReason="Preview expired"
      />,
    )
    const dialog = screen.getByRole('dialog', { name: 'Review outbound content' })
    const btn = within(dialog).getByRole('button', { name: 'Send to provider' }) as HTMLButtonElement
    expect(btn.disabled).toBe(true)
    expect(within(dialog).getByText('Preview expired')).toBeTruthy()
  })
})

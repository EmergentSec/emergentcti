import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { ReportForm } from './ReportForm'
import type { ReportDetail } from '@/types/report'

afterEach(cleanup)

const baseReport: ReportDetail = {
  id: 'rep-1',
  title: 'Weekly brief',
  origin: 'internal',
  source_name: null,
  published_at: null,
  summary: null,
  source_url: null,
  content: null,
  content_format: 'markdown',
  is_ai_generated: false,
  ai_provider: null,
  ai_model: null,
  ai_generated_at: null,
  tlp: 'red',
  tags: [],
  has_attachment: false,
  attachment: null,
  observables: [],
  created_by: null,
  created_at: '',
  updated_at: '',
}

describe('ReportForm — TLP downgrade reason dialog', () => {
  it('prompts for a reason when loosening a specified marking', () => {
    const handleSubmit = vi.fn()
    render(<ReportForm initial={baseReport} onSubmit={handleSubmit} onCancel={vi.fn()} isAdmin />)
    fireEvent.change(screen.getByLabelText(/tlp marking/i), { target: { value: 'green' } })
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)
    expect(screen.getByRole('dialog', { name: /reason for tlp change/i })).toBeTruthy()
    expect(handleSubmit).not.toHaveBeenCalled()
  })

  it('does not prompt when classifying Unspecified to a specified marking', () => {
    const handleSubmit = vi.fn()
    render(
      <ReportForm
        initial={{ ...baseReport, tlp: null }}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
        isAdmin
      />,
    )
    fireEvent.change(screen.getByLabelText(/tlp marking/i), { target: { value: 'amber' } })
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)
    expect(screen.queryByRole('dialog', { name: /reason for tlp change/i })).toBeNull()
    expect(handleSubmit).toHaveBeenCalledOnce()
    expect(handleSubmit.mock.calls[0][0].tlp).toBe('amber')
    expect(handleSubmit.mock.calls[0][0].tlp_change_reason).toBeUndefined()
  })

  it('cancel on the dialog aborts the save', () => {
    const handleSubmit = vi.fn()
    render(<ReportForm initial={baseReport} onSubmit={handleSubmit} onCancel={vi.fn()} isAdmin />)
    fireEvent.change(screen.getByLabelText(/tlp marking/i), { target: { value: 'clear' } })
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)
    const dialog = screen.getByRole('dialog', { name: /reason for tlp change/i })
    fireEvent.click(within(dialog).getByRole('button', { name: /^cancel$/i }))
    expect(handleSubmit).not.toHaveBeenCalled()
  })

  it('confirm sends tlp_change_reason with the update payload', () => {
    const handleSubmit = vi.fn()
    render(<ReportForm initial={baseReport} onSubmit={handleSubmit} onCancel={vi.fn()} isAdmin />)
    fireEvent.change(screen.getByLabelText(/tlp marking/i), { target: { value: 'green' } })
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)
    fireEvent.change(screen.getByLabelText(/^reason$/i), { target: { value: 'vendor cleared' } })
    fireEvent.click(screen.getByRole('button', { name: /^continue$/i }))
    expect(handleSubmit).toHaveBeenCalledOnce()
    expect(handleSubmit.mock.calls[0][0]).toMatchObject({
      tlp: 'green',
      tlp_change_reason: 'vendor cleared',
    })
  })
})

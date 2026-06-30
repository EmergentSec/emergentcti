import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { DetailRawTab } from './DetailRawTab'
import type { Observable } from '@/types/observable'

afterEach(cleanup)

const OBS: Observable = {
  id: 'obs-1',
  type: 'ip-addr',
  value: '5.188.206.18',
  confidence_score: 72,
  first_seen: '2026-06-27T00:00:00Z',
  last_seen: '2026-06-29T00:00:00Z',
  source_count: 1,
  sources: [],
  created_at: '2026-06-27T00:00:00Z',
  updated_at: '2026-06-29T00:00:00Z',
}

describe('DetailRawTab', () => {
  it('renders the GET endpoint label', () => {
    render(<DetailRawTab observable={OBS} />)
    expect(screen.getByText('GET /api/v1/observables/:id')).toBeTruthy()
  })

  it('renders JSON containing a known field (observable id)', () => {
    const { container } = render(<DetailRawTab observable={OBS} />)
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
    expect(pre?.textContent).toContain('obs-1')
  })

  it('renders JSON containing observable value field', () => {
    const { container } = render(<DetailRawTab observable={OBS} />)
    const pre = container.querySelector('pre')
    expect(pre?.textContent).toContain('5.188.206.18')
  })

  it('renders a Copy button', () => {
    render(<DetailRawTab observable={OBS} />)
    expect(screen.getByRole('button', { name: /copy json/i })).toBeTruthy()
  })

  it('shows "Copy" label on the button initially', () => {
    render(<DetailRawTab observable={OBS} />)
    expect(screen.getByText('Copy')).toBeTruthy()
  })

  it('switches to "Copied" label after clicking copy', () => {
    // Mock clipboard API
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    })
    render(<DetailRawTab observable={OBS} />)
    const btn = screen.getByRole('button', { name: /copy json/i })
    fireEvent.click(btn)
    expect(screen.getByText('Copied')).toBeTruthy()
  })
})

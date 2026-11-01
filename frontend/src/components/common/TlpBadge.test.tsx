import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TlpBadge } from './TlpBadge'
import { TLP_MEANINGS } from '@/lib/tlp'

describe('TlpBadge', () => {
  it('renders unspecified with visible label and screen-reader meaning', () => {
    render(<TlpBadge tlp={null} />)
    const badge = screen.getByText('Unspecified')
    expect(badge.textContent).toMatch(/sharing policy/i)
    expect(badge.getAttribute('title')).toMatch(/sharing policy/i)
  })

  it('renders TLP:RED label text with its meaning', () => {
    render(<TlpBadge tlp="red" />)
    const badge = screen.getByText('TLP:RED')
    expect(badge.textContent).toContain(TLP_MEANINGS.red)
  })

  it('is not focusable or interactive (no tab stop per table row)', () => {
    const { container } = render(<TlpBadge tlp="amber" />)
    expect(screen.queryByRole('button')).toBeNull()
    expect(container.querySelector('[tabindex]')).toBeNull()
  })

  it('shows STRICT suffix for amber+strict', () => {
    render(<TlpBadge tlp="amber+strict" />)
    expect(screen.getByText('STRICT')).toBeTruthy()
  })
})

import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TlpBadge } from './TlpBadge'

describe('TlpBadge', () => {
  it('renders unspecified with accessible label and meaning', () => {
    render(<TlpBadge tlp={null} />)
    const badge = screen.getByRole('button', { name: 'Unspecified' })
    expect(badge.getAttribute('aria-describedby')).toBeTruthy()
    expect(document.getElementById(badge.getAttribute('aria-describedby')!)?.textContent).toMatch(
      /sharing policy/i,
    )
  })

  it('renders TLP:RED label text', () => {
    render(<TlpBadge tlp="red" />)
    expect(screen.getByRole('button', { name: 'TLP:RED' })).toBeTruthy()
  })

  it('shows STRICT suffix for amber+strict', () => {
    render(<TlpBadge tlp="amber+strict" />)
    expect(screen.getByText('STRICT')).toBeTruthy()
  })
})

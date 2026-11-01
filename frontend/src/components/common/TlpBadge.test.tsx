import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TlpBadge } from './TlpBadge'

describe('TlpBadge', () => {
  it('renders unspecified with accessible label', () => {
    render(<TlpBadge tlp={null} />)
    expect(screen.getByLabelText(/Unspecified\./)).toBeTruthy()
  })

  it('renders TLP:RED label text', () => {
    render(<TlpBadge tlp="red" />)
    expect(screen.getByLabelText(/TLP:RED\./)).toBeTruthy()
  })

  it('shows STRICT suffix for amber+strict', () => {
    render(<TlpBadge tlp="amber+strict" />)
    expect(screen.getByText('STRICT')).toBeTruthy()
  })
})

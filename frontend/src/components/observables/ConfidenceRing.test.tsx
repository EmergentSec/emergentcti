import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { ConfidenceRing } from './ConfidenceRing'

afterEach(cleanup)

describe('ConfidenceRing', () => {
  it('renders the decayed score', () => {
    render(<ConfidenceRing decayed={38} nativeMax={45} />)
    // Appears in center overlay and readout
    const hits = screen.getAllByText('38')
    expect(hits.length).toBeGreaterThan(0)
  })

  it('renders the nativeMax score', () => {
    render(<ConfidenceRing decayed={38} nativeMax={45} />)
    expect(screen.getByTestId('readout-native').textContent).toBe('45')
  })

  it('applies conf-low color for score in 0–39 band', () => {
    const { container } = render(<ConfidenceRing decayed={38} nativeMax={45} />)
    const styledEl = container.querySelector('[style*="--conf-low"]')
    expect(styledEl).not.toBeNull()
  })

  it('applies conf-medium color for score in 40–59 band', () => {
    const { container } = render(<ConfidenceRing decayed={52} nativeMax={60} />)
    const styledEl = container.querySelector('[style*="--conf-medium"]')
    expect(styledEl).not.toBeNull()
  })

  it('applies conf-high color for score in 60–79 band', () => {
    const { container } = render(<ConfidenceRing decayed={72} nativeMax={80} />)
    const styledEl = container.querySelector('[style*="--conf-high"]')
    expect(styledEl).not.toBeNull()
  })

  it('applies conf-critical color for score in 80–100 band', () => {
    const { container } = render(<ConfidenceRing decayed={90} nativeMax={90} />)
    const styledEl = container.querySelector('[style*="--conf-critical"]')
    expect(styledEl).not.toBeNull()
  })

  it('renders the "Effective confidence" title', () => {
    render(<ConfidenceRing decayed={38} nativeMax={45} />)
    expect(screen.getByText('Effective confidence')).toBeTruthy()
  })

  it('renders "decayed" and "native max" readout labels', () => {
    render(<ConfidenceRing decayed={38} nativeMax={45} />)
    expect(screen.getByText('decayed')).toBeTruthy()
    expect(screen.getByText('native max')).toBeTruthy()
  })
})

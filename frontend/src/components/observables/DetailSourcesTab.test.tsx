import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { DetailSourcesTab } from './DetailSourcesTab'
import type { ObservableSource } from '@/types/observable'

afterEach(cleanup)

const LOW_SOURCE: ObservableSource = {
  feed_id: 'f1',
  feed_name: 'Blocklist.de',
  source_confidence: 38,
  native_confidence: 38,
  first_seen_by_feed: '2026-06-27T00:00:00Z',
  last_seen_by_feed: '2026-06-28T00:00:00Z',
}

describe('DetailSourcesTab', () => {
  it('renders feed_name in the table', () => {
    render(<DetailSourcesTab sources={[LOW_SOURCE]} />)
    expect(screen.getByText('Blocklist.de')).toBeTruthy()
  })

  it('renders native_confidence value', () => {
    render(<DetailSourcesTab sources={[LOW_SOURCE]} />)
    expect(screen.getByText('38')).toBeTruthy()
  })

  it('applies conf-low color for native_confidence in 0–39 band', () => {
    const { container } = render(<DetailSourcesTab sources={[LOW_SOURCE]} />)
    const el = container.querySelector('[style*="--conf-low"]')
    expect(el).not.toBeNull()
  })

  it('applies conf-medium color for native_confidence in 40–59 band', () => {
    const source: ObservableSource = { ...LOW_SOURCE, native_confidence: 52 }
    const { container } = render(<DetailSourcesTab sources={[source]} />)
    expect(container.querySelector('[style*="--conf-medium"]')).not.toBeNull()
  })

  it('applies conf-high color for native_confidence in 60–79 band', () => {
    const source: ObservableSource = { ...LOW_SOURCE, native_confidence: 72 }
    const { container } = render(<DetailSourcesTab sources={[source]} />)
    expect(container.querySelector('[style*="--conf-high"]')).not.toBeNull()
  })

  it('applies conf-critical color for native_confidence in 80–100 band', () => {
    const source: ObservableSource = { ...LOW_SOURCE, native_confidence: 85 }
    const { container } = render(<DetailSourcesTab sources={[source]} />)
    expect(container.querySelector('[style*="--conf-critical"]')).not.toBeNull()
  })

  it('does not render a type chip (no feed_type field)', () => {
    render(<DetailSourcesTab sources={[LOW_SOURCE]} />)
    // None of the typeLabel values should appear
    expect(screen.queryByText('IP Address')).toBeNull()
    expect(screen.queryByText('Domain')).toBeNull()
    expect(screen.queryByText('URL')).toBeNull()
    expect(screen.queryByText('File Hash')).toBeNull()
    expect(screen.queryByText('Email')).toBeNull()
    expect(screen.queryByText('Command Line')).toBeNull()
  })

  it('renders empty state when no sources', () => {
    render(<DetailSourcesTab sources={[]} />)
    expect(screen.getByText('Manually added — no feed sources')).toBeTruthy()
  })

  it('renders multiple sources', () => {
    const second: ObservableSource = {
      feed_id: 'f2',
      feed_name: 'URLhaus',
      source_confidence: 75,
      native_confidence: 75,
      first_seen_by_feed: '2026-06-29T00:00:00Z',
      last_seen_by_feed: '2026-06-29T20:00:00Z',
    }
    render(<DetailSourcesTab sources={[LOW_SOURCE, second]} />)
    expect(screen.getByText('Blocklist.de')).toBeTruthy()
    expect(screen.getByText('URLhaus')).toBeTruthy()
  })
})

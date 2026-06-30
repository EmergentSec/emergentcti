import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ObservableFilters } from './ObservableFilters'
import type { ObservableFilters as Filters } from '@/types/observable'

vi.mock('@/hooks/useFeeds', () => ({
  useFeeds: () => ({
    data: [
      { id: 'feed-uuid-1', name: 'URLhaus' },
      { id: 'feed-uuid-2', name: 'Feodo Tracker' },
    ],
  }),
}))

afterEach(cleanup)

const defaultFilters: Filters = {
  page: 1,
  size: 50,
  sort: 'last_seen',
  order: 'desc',
}

describe('ObservableFilters', () => {
  it('renders row 1 controls: search input, type select, source select with feeds', () => {
    render(<ObservableFilters filters={defaultFilters} onChange={vi.fn()} />)
    expect(screen.getByPlaceholderText('Search by value…')).toBeTruthy()
    expect(screen.getByText('All types')).toBeTruthy()
    expect(screen.getByText('All sources')).toBeTruthy()
    // Feed names appear as source options
    expect(screen.getByText('URLhaus')).toBeTruthy()
    expect(screen.getByText('Feodo Tracker')).toBeTruthy()
    // Type options from typeLabels
    expect(screen.getByText('IP Address')).toBeTruthy()
    expect(screen.getByText('Domain')).toBeTruthy()
  })

  it('renders row 2: slider, mono confidence readout, export split-button', () => {
    render(<ObservableFilters filters={defaultFilters} onChange={vi.fn()} />)
    expect(screen.getByRole('slider')).toBeTruthy()
    // Mono readout shows 0 when no confidence_min set
    expect(screen.getByText('0')).toBeTruthy()
    expect(screen.getByText('Export')).toBeTruthy()
  })

  it('shows active confidence value in mono readout', () => {
    render(<ObservableFilters filters={{ ...defaultFilters, confidence_min: 55 }} onChange={vi.fn()} />)
    expect(screen.getByText('55')).toBeTruthy()
    expect(screen.getByRole('slider')).toBeTruthy()
  })

  it('export popover opens and shows blocklist and JSON export rows', () => {
    render(<ObservableFilters filters={defaultFilters} onChange={vi.fn()} />)
    // Popover closed initially — content not visible
    expect(screen.queryByText('IP Addresses')).toBeNull()
    // Click Export to open popover
    fireEvent.click(screen.getByText('Export'))
    // Blocklist group
    expect(screen.getByText('IP Addresses')).toBeTruthy()
    expect(screen.getByText('Domains')).toBeTruthy()
    expect(screen.getByText('URLs')).toBeTruthy()
    // JSON group
    expect(screen.getByText('Full JSON export')).toBeTruthy()
  })

  it('export links carry current confidence_min and feed_id filters', () => {
    const filters: Filters = { ...defaultFilters, confidence_min: 60, source: 'feed-uuid-1' }
    render(<ObservableFilters filters={filters} onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('Export'))

    const ipLink = screen.getByText('IP Addresses').closest('a')!
    expect(ipLink.getAttribute('href')).toBe(
      '/api/v1/export/blocklist/ip-addr?confidence_min=60&feed_id=feed-uuid-1',
    )

    const domainLink = screen.getByText('Domains').closest('a')!
    expect(domainLink.getAttribute('href')).toBe(
      '/api/v1/export/blocklist/domain-name?confidence_min=60&feed_id=feed-uuid-1',
    )

    const jsonLink = screen.getByText('Full JSON export').closest('a')!
    expect(jsonLink.getAttribute('href')).toBe(
      '/api/v1/export/json?confidence_min=60&feed_id=feed-uuid-1',
    )
  })

  it('export links omit feed_id when source is manual', () => {
    const filters: Filters = { ...defaultFilters, confidence_min: 40, source: 'manual' }
    render(<ObservableFilters filters={filters} onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('Export'))

    const ipLink = screen.getByText('IP Addresses').closest('a')!
    expect(ipLink.getAttribute('href')).toBe(
      '/api/v1/export/blocklist/ip-addr?confidence_min=40',
    )

    const jsonLink = screen.getByText('Full JSON export').closest('a')!
    expect(jsonLink.getAttribute('href')).toBe('/api/v1/export/json?confidence_min=40')
  })

  it('calls onChange with updated q when search input changes', () => {
    const onChange = vi.fn()
    render(<ObservableFilters filters={defaultFilters} onChange={onChange} />)
    const input = screen.getByPlaceholderText('Search by value…')
    fireEvent.change(input, { target: { value: '1.2.3.4' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ q: '1.2.3.4', page: 1 }),
    )
  })
})

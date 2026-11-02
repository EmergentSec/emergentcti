import { afterEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { AuditHistory } from './AuditHistory'
import type { AuditEventsResponse } from '@/api/audit'

const sampleList: AuditEventsResponse = {
  items: [
    {
      id: 'ev-1',
      occurred_at: '2026-11-02T15:00:00Z',
      actor_type: 'user',
      actor_id: 'u-1',
      actor_label: 'admin',
      action: 'report.update',
      resource_type: 'report',
      resource_id: 'r-1',
      resource_label: 'APT notes',
      outcome: 'succeeded',
      summary: { changed_fields: ['title'], html: '<b>bold</b>' },
    },
    {
      id: 'ev-2',
      occurred_at: '2026-11-02T14:00:00Z',
      actor_type: 'system',
      actor_id: null,
      actor_label: 'retention',
      action: 'export.download',
      resource_type: 'export',
      resource_id: 'json',
      resource_label: null,
      outcome: 'initiated',
      summary: {},
    },
  ],
  total: 2,
  page: 1,
  size: 50,
  pages: 1,
}

const mockUseAuditMeta = vi.fn()
const mockUseAuditEvents = vi.fn()

vi.mock('@/hooks/useAudit', () => ({
  useAuditMeta: () => mockUseAuditMeta(),
  useAuditEvents: (filters: unknown) => mockUseAuditEvents(filters),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AuditHistory', () => {
  it('shows loading spinner while fetching', () => {
    mockUseAuditMeta.mockReturnValue({ data: undefined })
    mockUseAuditEvents.mockReturnValue({ data: undefined, isLoading: true, error: null })

    render(<AuditHistory />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeTruthy()
  })

  it('shows error empty state', () => {
    mockUseAuditMeta.mockReturnValue({ data: { actions: [], actor_types: [], outcomes: [], resource_types: [], retention_days: 365 } })
    const err = new axios.AxiosError('Forbidden')
    err.response = { status: 403, data: { detail: 'Forbidden' }, statusText: '', headers: {}, config: {} as never }
    mockUseAuditEvents.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: err,
    })

    render(<AuditHistory />)
    expect(screen.getByText('Failed to load audit history')).toBeTruthy()
    expect(screen.getByText('Forbidden')).toBeTruthy()
  })

  it('shows empty state when there are no events', () => {
    mockUseAuditMeta.mockReturnValue({ data: { actions: [], actor_types: [], outcomes: [], resource_types: [], retention_days: 365 } })
    mockUseAuditEvents.mockReturnValue({
      data: { items: [], total: 0, page: 1, size: 50, pages: 1 },
      isLoading: false,
      error: null,
    })

    render(<AuditHistory />)
    expect(screen.getByText('No audit events')).toBeTruthy()
  })

  it('renders outcome badges and delivery help text', () => {
    mockUseAuditMeta.mockReturnValue({
      data: {
        actions: ['report.update', 'export.download'],
        actor_types: ['user', 'system'],
        outcomes: ['succeeded', 'initiated'],
        resource_types: ['report', 'export'],
        retention_days: 365,
      },
    })
    mockUseAuditEvents.mockReturnValue({ data: sampleList, isLoading: false, error: null })

    render(<AuditHistory />)

    expect(screen.getByText(/delivery was not proven/)).toBeTruthy()
    const table = screen.getByRole('table')
    expect(within(table).getByText('succeeded')).toBeTruthy()
    expect(within(table).getByText('initiated')).toBeTruthy()
  })

  it('renders summary values as plain text including HTML-like strings', () => {
    mockUseAuditMeta.mockReturnValue({
      data: {
        actions: ['report.update'],
        actor_types: ['user'],
        outcomes: ['succeeded'],
        resource_types: ['report'],
        retention_days: 365,
      },
    })
    mockUseAuditEvents.mockReturnValue({ data: sampleList, isLoading: false, error: null })

    render(<AuditHistory />)

    fireEvent.click(screen.getByText('admin (user)'))
    expect(screen.getByText('Event summary')).toBeTruthy()
    expect(screen.getByText('<b>bold</b>')).toBeTruthy()
    expect(document.querySelector('b')).toBeNull()
  })

  it('passes composed filters including pagination to the events hook', () => {
    mockUseAuditMeta.mockReturnValue({
      data: {
        actions: ['report.update'],
        actor_types: ['user'],
        outcomes: ['succeeded'],
        resource_types: ['report'],
        retention_days: 365,
      },
    })
    mockUseAuditEvents.mockReturnValue({ data: sampleList, isLoading: false, error: null })

    render(<AuditHistory />)

    fireEvent.change(screen.getByLabelText('Filter by actor id'), { target: { value: 'u-99' } })

    const lastCall = mockUseAuditEvents.mock.calls[mockUseAuditEvents.mock.calls.length - 1]?.[0] as Record<string, unknown>
    expect(lastCall.actor_id).toBe('u-99')
    expect(lastCall.page).toBe(1)
  })

  it('shows UTC ISO on time title attribute', () => {
    mockUseAuditMeta.mockReturnValue({
      data: {
        actions: ['report.update'],
        actor_types: ['user'],
        outcomes: ['succeeded'],
        resource_types: ['report'],
        retention_days: 365,
      },
    })
    mockUseAuditEvents.mockReturnValue({ data: sampleList, isLoading: false, error: null })

    render(<AuditHistory />)

    const timeEl = screen.getByTitle('2026-11-02T15:00:00Z')
    expect(timeEl.tagName.toLowerCase()).toBe('time')
    expect(timeEl.getAttribute('datetime')).toBe('2026-11-02T15:00:00Z')
  })

  it('renders pagination when multiple pages exist', () => {
    mockUseAuditMeta.mockReturnValue({
      data: {
        actions: [],
        actor_types: [],
        outcomes: [],
        resource_types: [],
        retention_days: 365,
      },
    })
    mockUseAuditEvents.mockReturnValue({
      data: { ...sampleList, pages: 3, total: 120 },
      isLoading: false,
      error: null,
    })

    render(<AuditHistory />)
    expect(screen.getByRole('navigation', { name: 'Pagination' })).toBeTruthy()
    expect(within(screen.getByRole('navigation', { name: 'Pagination' })).getByText(/Page 1 of 3/)).toBeTruthy()
  })
})

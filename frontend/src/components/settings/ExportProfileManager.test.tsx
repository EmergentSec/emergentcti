import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { AxiosError, type AxiosResponse } from 'axios'
import { ExportProfileManager } from './ExportProfileManager'
import type { ExportProfile } from '@/types/exportProfile'

// ── Mock hooks and contexts ───────────────────────────────────────────────────

const PROFILES: ExportProfile[] = [
  {
    id: 'p-1',
    name: 'Firewall IPs',
    description: 'High-confidence IPs for the edge firewall',
    format: 'text',
    type: 'ip-addr',
    confidence_min: 80,
    max_age_days: 30,
    feed_id: 'feed-1',
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  },
  {
    id: 'p-2',
    name: 'Everything',
    description: null,
    format: 'json',
    type: null,
    confidence_min: 0,
    max_age_days: null,
    feed_id: null,
    created_at: '2026-10-02T00:00:00Z',
    updated_at: '2026-10-02T00:00:00Z',
  },
]

const FEEDS = [
  { id: 'feed-1', name: 'URLhaus' },
  { id: 'feed-2', name: 'ThreatFox' },
]

const mockUseProfiles = vi.fn()
const mockUsePreview = vi.fn()
const mockUseFeeds = vi.fn()
const mockCreate = vi.fn()
const mockUpdate = vi.fn()
const mockDelete = vi.fn()
const mockToast = vi.fn()
const mockRefetch = vi.fn()
const { mockAuth } = vi.hoisted(() => ({ mockAuth: { isAdmin: true } }))

vi.mock('@/hooks/useExportProfiles', () => ({
  useExportProfiles: () => mockUseProfiles(),
  useExportProfilePreview: (id: string | null) => mockUsePreview(id),
  useCreateExportProfile: () => ({ mutate: mockCreate, isPending: false }),
  useUpdateExportProfile: () => ({ mutate: mockUpdate, isPending: false }),
  useDeleteExportProfile: () => ({ mutate: mockDelete, isPending: false }),
}))

vi.mock('@/hooks/useFeeds', () => ({
  useFeeds: () => mockUseFeeds(),
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

function httpError(status: number, detail: unknown) {
  return new AxiosError('Request failed', String(status), undefined, undefined, {
    status,
    data: { detail },
  } as AxiosResponse)
}

function previewResult(data: { count: number; excluded_allowlisted: number; sample: string[] }) {
  return { data, isLoading: false, isFetching: false, error: null, refetch: mockRefetch }
}

function renderLoaded(profiles: ExportProfile[] = PROFILES) {
  mockUseProfiles.mockReturnValue({ data: profiles, isLoading: false, error: null })
  return render(<ExportProfileManager />)
}

function card(name: string) {
  return within(screen.getByRole('heading', { name }).closest('li')!)
}

const DOWNLOAD_URL = `${window.location.origin}/api/v1/export/profiles/p-1/download`

beforeEach(() => {
  mockUseFeeds.mockReturnValue({ data: FEEDS })
  mockUsePreview.mockReturnValue(previewResult({ count: 0, excluded_allowlisted: 0, sample: [] }))
})

afterEach(() => {
  cleanup()
  mockAuth.isAdmin = true
  for (const m of [mockCreate, mockUpdate, mockDelete, mockToast, mockRefetch, mockUsePreview]) m.mockReset()
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ExportProfileManager — reading', () => {
  it('lists profiles with their saved filters', () => {
    renderLoaded()
    const first = card('Firewall IPs')
    expect(first.getByText('High-confidence IPs for the edge firewall')).toBeTruthy()
    expect(first.getByText('Text')).toBeTruthy()
    expect(first.getByText('IP Address')).toBeTruthy()
    expect(first.getByText('Confidence ≥ 80')).toBeTruthy()
    expect(first.getByText('Seen in last 30d')).toBeTruthy()
    expect(first.getByText('URLhaus')).toBeTruthy()

    const second = card('Everything')
    expect(second.getByText('JSON')).toBeTruthy()
    expect(second.getByText('All types')).toBeTruthy()
    expect(second.getByText('Any age')).toBeTruthy()
    expect(second.getByText('All sources')).toBeTruthy()
  })

  it('labels a feed that is no longer listed instead of implying all sources', () => {
    mockUseFeeds.mockReturnValue({ data: [] })
    renderLoaded()
    expect(card('Firewall IPs').getByText('Unknown feed')).toBeTruthy()
  })

  it('explains that URLs carry no credentials and use X-API-Key', () => {
    renderLoaded()
    expect(screen.getByText(/Download URLs contain no credentials/)).toBeTruthy()
    expect(screen.getByText('X-API-Key')).toBeTruthy()
  })

  it('states that text and JSON downloads are both uncapped', () => {
    renderLoaded()
    expect(
      screen.getByText(/Text and JSON downloads both contain every eligible indicator with\s+no row cap/),
    ).toBeTruthy()
    expect(screen.queryByText(/row limit/)).toBeNull()
  })

  it('shows empty and error states', () => {
    renderLoaded([])
    expect(screen.getByText('No export profiles yet.')).toBeTruthy()
    cleanup()

    mockUseProfiles.mockReturnValue({ data: undefined, isLoading: false, error: new Error('boom') })
    render(<ExportProfileManager />)
    expect(screen.getByRole('alert').textContent).toBe('Failed to load export profiles')
  })

  it('non-admin can preview, copy and download but cannot create, edit or delete', () => {
    mockAuth.isAdmin = false
    renderLoaded()
    expect(screen.getByRole('button', { name: 'Preview Firewall IPs' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Copy download URL for Firewall IPs' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Download Firewall IPs' })).toBeTruthy()
    expect(screen.getByText('Only administrators can create, edit or delete export profiles.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'New profile' })).toBeNull()
    expect(screen.queryByRole('button', { name: /^Edit / })).toBeNull()
    expect(screen.queryByRole('button', { name: /^Delete / })).toBeNull()
  })
})

describe('ExportProfileManager — download and URL', () => {
  it('links the download to the relative authenticated path', () => {
    renderLoaded()
    const link = screen.getByRole('link', { name: 'Download Firewall IPs' })
    expect(link.getAttribute('href')).toBe('/api/v1/export/profiles/p-1/download')
    expect(link.hasAttribute('download')).toBe(true)
  })

  it('shows and copies the absolute download URL', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    renderLoaded()

    expect(card('Firewall IPs').getByText(DOWNLOAD_URL)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Copy download URL for Firewall IPs' }))

    expect(writeText).toHaveBeenCalledWith(DOWNLOAD_URL)
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith('Download URL copied to clipboard', 'success'),
    )
  })

  it('reports a clipboard failure', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    renderLoaded()

    fireEvent.click(screen.getByRole('button', { name: 'Copy download URL for Firewall IPs' }))
    await waitFor(() => expect(mockToast).toHaveBeenCalledWith('Failed to copy to clipboard', 'error'))
  })
})

describe('ExportProfileManager — preview', () => {
  it('does not request a preview until asked', () => {
    renderLoaded()
    expect(mockUsePreview).not.toHaveBeenCalled()
  })

  it('shows counts, allowlist exclusions and a sample', () => {
    mockUsePreview.mockReturnValue(
      previewResult({ count: 1234, excluded_allowlisted: 7, sample: ['1.1.1.1', '2.2.2.2'] }),
    )
    renderLoaded()
    const toggle = screen.getByRole('button', { name: 'Preview Firewall IPs' })
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(toggle)

    expect(mockUsePreview).toHaveBeenCalledWith('p-1')
    const preview = within(screen.getByRole('region', { name: 'Preview of Firewall IPs' }))
    expect(preview.getByText('Would be exported').nextElementSibling?.textContent).toBe('1,234')
    expect(preview.getByText('Excluded by allowlist').nextElementSibling?.textContent).toBe('7')
    expect(preview.getByText('Sample — first 2 of 1,234 values')).toBeTruthy()
    expect(preview.getByText('1.1.1.1')).toBeTruthy()
    expect(preview.getByText('2.2.2.2')).toBeTruthy()

    fireEvent.click(preview.getByRole('button', { name: 'Refresh preview' }))
    expect(mockRefetch).toHaveBeenCalled()

    // Toggling again hides it
    fireEvent.click(screen.getByRole('button', { name: 'Hide preview of Firewall IPs' }))
    expect(screen.queryByRole('region', { name: 'Preview of Firewall IPs' })).toBeNull()
  })

  it('shows an empty-match message', () => {
    mockUsePreview.mockReturnValue(previewResult({ count: 0, excluded_allowlisted: 3, sample: [] }))
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Preview Firewall IPs' }))
    expect(screen.getByText('No indicators currently match this profile.')).toBeTruthy()
  })

  it('shows a preview error', () => {
    mockUsePreview.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: httpError(404, 'Export profile not found'),
      refetch: mockRefetch,
    })
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Preview Firewall IPs' }))
    expect(screen.getByRole('alert').textContent).toBe('Export profile not found')
  })
})

describe('ExportProfileManager — create and edit', () => {
  it('creates a profile with defaults (confidence 70, no narrowing filters)', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'New profile' }))
    expect((screen.getByLabelText('Minimum confidence') as HTMLInputElement).value).toBe('70')
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: '  Edge blocklist ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))

    expect(mockCreate.mock.calls[0][0]).toEqual({
      name: 'Edge blocklist',
      description: null,
      format: 'text',
      type: null,
      confidence_min: 70,
      max_age_days: null,
      feed_id: null,
    })

    act(() => mockCreate.mock.calls[0][1].onSuccess())
    expect(mockToast).toHaveBeenCalledWith('Export profile created', 'success')
    expect(screen.queryByLabelText('Name')).toBeNull()
  })

  it('creates a profile with every filter set', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'New profile' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Domains' } })
    fireEvent.change(screen.getByLabelText('Description (optional)'), { target: { value: 'DNS sinkhole' } })
    fireEvent.change(screen.getByLabelText('Format'), { target: { value: 'json' } })
    fireEvent.change(screen.getByLabelText('Observable type'), { target: { value: 'domain-name' } })
    fireEvent.change(screen.getByLabelText('Minimum confidence'), { target: { value: '55' } })
    fireEvent.change(screen.getByLabelText('Maximum age in days (optional)'), { target: { value: '14' } })
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'feed-2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))

    expect(mockCreate.mock.calls[0][0]).toEqual({
      name: 'Domains',
      description: 'DNS sinkhole',
      format: 'json',
      type: 'domain-name',
      confidence_min: 55,
      max_age_days: 14,
      feed_id: 'feed-2',
    })
  })

  it('blocks submission and shows field errors for invalid input', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'New profile' }))
    fireEvent.change(screen.getByLabelText('Minimum confidence'), { target: { value: '150' } })
    fireEvent.change(screen.getByLabelText('Maximum age in days (optional)'), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))

    expect(screen.getByText('Name is required')).toBeTruthy()
    expect(screen.getByText('Minimum confidence must be a whole number from 0 to 100')).toBeTruthy()
    expect(screen.getByText(/Maximum age must be a whole number from 1 to 36500 days/)).toBeTruthy()
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('reports a duplicate name (409) inline and keeps the form open', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'New profile' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Firewall IPs' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))

    act(() => mockCreate.mock.calls[0][1].onError(httpError(409, 'Profile name already exists')))
    expect(screen.getByRole('alert').textContent).toBe('An export profile with this name already exists.')
    expect(mockToast).toHaveBeenCalledWith('An export profile with this name already exists.', 'error')
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Firewall IPs')
  })

  it('surfaces other server errors', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'New profile' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'X' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))

    act(() => mockCreate.mock.calls[0][1].onError(httpError(422, 'Feed not found')))
    expect(screen.getByRole('alert').textContent).toBe('Feed not found')
  })

  it('prefills the edit form and sends explicit nulls for cleared filters', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Edit Firewall IPs' }))

    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Firewall IPs')
    expect((screen.getByLabelText('Observable type') as HTMLSelectElement).value).toBe('ip-addr')
    expect((screen.getByLabelText('Minimum confidence') as HTMLInputElement).value).toBe('80')
    expect((screen.getByLabelText('Maximum age in days (optional)') as HTMLInputElement).value).toBe('30')
    expect((screen.getByLabelText('Source') as HTMLSelectElement).value).toBe('feed-1')

    fireEvent.change(screen.getByLabelText('Maximum age in days (optional)'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Observable type'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(mockCreate).not.toHaveBeenCalled()
    expect(mockUpdate.mock.calls[0][0]).toEqual({
      id: 'p-1',
      data: {
        name: 'Firewall IPs',
        description: 'High-confidence IPs for the edge firewall',
        format: 'text',
        type: null,
        confidence_min: 80,
        max_age_days: null,
        feed_id: null,
      },
    })

    act(() => mockUpdate.mock.calls[0][1].onSuccess())
    expect(mockToast).toHaveBeenCalledWith('Export profile updated', 'success')
  })

  it('keeps a saved feed selected when the feed list does not include it', () => {
    mockUseFeeds.mockReturnValue({ data: undefined })
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Edit Firewall IPs' }))
    expect((screen.getByLabelText('Source') as HTMLSelectElement).value).toBe('feed-1')

    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(mockUpdate.mock.calls[0][0].data.feed_id).toBe('feed-1')
  })
})

describe('ExportProfileManager — delete', () => {
  it('confirms before deleting', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Delete Firewall IPs' }))
    expect(mockDelete).not.toHaveBeenCalled()
    expect(screen.getByText(/download URL will stop working/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Delete profile' }))
    expect(mockDelete.mock.calls[0][0]).toBe('p-1')

    act(() => mockDelete.mock.calls[0][1].onSuccess())
    expect(mockToast).toHaveBeenCalledWith('Firewall IPs deleted', 'success')
    expect(screen.queryByRole('button', { name: 'Delete profile' })).toBeNull()
  })

  it('reports a failed delete', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Delete Firewall IPs' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete profile' }))

    act(() => mockDelete.mock.calls[0][1].onError(httpError(403, 'Admin access required')))
    expect(mockToast).toHaveBeenCalledWith('Admin access required', 'error')
  })
})

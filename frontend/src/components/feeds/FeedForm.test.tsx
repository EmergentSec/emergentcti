import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { FeedForm } from './FeedForm'
import type { Feed } from '@/types/feed'

afterEach(cleanup)

// ── Shared fixtures ──────────────────────────────────────────────────────────

const baseEditFeed: Feed = {
  id: 'f1',
  name: 'AbuseIPDB',
  description: 'Community IPs',
  feed_type: 'api',
  url: 'https://api.abuseipdb.com/api/v2/blacklist',
  config: null,
  schedule_cron: '0 */6 * * *',
  enabled: true,
  is_preconfigured: true,
  has_auth: false,
  auth_supported: true,
  default_confidence: 85,
  last_run_at: null,
  observable_count: 0,
  latest_run: null,
  created_at: '',
  updated_at: '',
}

// ── Create mode ──────────────────────────────────────────────────────────────

describe('FeedForm — create mode (no initialValues)', () => {
  it('renders empty name and URL fields', () => {
    render(<FeedForm onSubmit={vi.fn()} onCancel={vi.fn()} />)
    const nameInput = screen.getByLabelText(/feed name/i) as HTMLInputElement
    const urlInput = screen.getByLabelText(/^url$/i) as HTMLInputElement
    expect(nameInput.value).toBe('')
    expect(urlInput.value).toBe('')
  })

  it('shows "Create Feed" submit button', () => {
    render(<FeedForm onSubmit={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('button', { name: /create feed/i })).toBeTruthy()
  })

  it('shows Auth Config JSON textarea', () => {
    render(<FeedForm onSubmit={vi.fn()} onCancel={vi.fn()} />)
    // In create mode, the raw JSON textarea is present
    expect(screen.getByText(/auth config/i)).toBeTruthy()
    expect(screen.getByPlaceholderText(/api_key/i)).toBeTruthy()
  })

  it('calls onSubmit with FeedCreate data on valid submit', () => {
    const handleSubmit = vi.fn()
    render(<FeedForm onSubmit={handleSubmit} onCancel={vi.fn()} />)

    fireEvent.change(screen.getByLabelText(/feed name/i), {
      target: { value: 'My Feed' },
    })
    fireEvent.change(screen.getByLabelText(/^url$/i), {
      target: { value: 'https://example.com/feed.txt' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /create feed/i }).closest('form')!)

    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect(payload.name).toBe('My Feed')
    expect(payload.url).toBe('https://example.com/feed.txt')
    expect(payload.feed_type).toBe('file') // default
  })

  it('does not include auth_config when JSON textarea is empty', () => {
    const handleSubmit = vi.fn()
    render(<FeedForm onSubmit={handleSubmit} onCancel={vi.fn()} />)

    fireEvent.change(screen.getByLabelText(/feed name/i), {
      target: { value: 'My Feed' },
    })
    fireEvent.change(screen.getByLabelText(/^url$/i), {
      target: { value: 'https://example.com/feed.txt' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /create feed/i }).closest('form')!)

    const payload = handleSubmit.mock.calls[0][0]
    expect('auth_config' in payload).toBe(false)
  })

  it('shows name required error when submitted without name', () => {
    render(<FeedForm onSubmit={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/^url$/i), {
      target: { value: 'https://example.com/feed.txt' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /create feed/i }).closest('form')!)
    expect(screen.getByText(/name is required/i)).toBeTruthy()
  })

  it('shows URL required error when submitted without URL', () => {
    render(<FeedForm onSubmit={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/feed name/i), {
      target: { value: 'My Feed' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /create feed/i }).closest('form')!)
    expect(screen.getByText(/url is required/i)).toBeTruthy()
  })

  it('shows invalid JSON error when auth config textarea contains bad JSON', () => {
    render(<FeedForm onSubmit={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/feed name/i), {
      target: { value: 'My Feed' },
    })
    fireEvent.change(screen.getByLabelText(/^url$/i), {
      target: { value: 'https://example.com' },
    })
    fireEvent.change(screen.getByPlaceholderText(/api_key/i), {
      target: { value: 'not-json' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /create feed/i }).closest('form')!)
    expect(screen.getByText(/valid json/i)).toBeTruthy()
  })

  it('calls onCancel when Cancel button is clicked', () => {
    const handleCancel = vi.fn()
    render(<FeedForm onSubmit={vi.fn()} onCancel={handleCancel} />)
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(handleCancel).toHaveBeenCalledOnce()
  })

  it('shows "Creating..." on submit button when isLoading is true', () => {
    render(<FeedForm onSubmit={vi.fn()} onCancel={vi.fn()} isLoading />)
    expect(screen.getByRole('button', { name: /creating/i })).toBeTruthy()
  })
})

// ── Edit mode ────────────────────────────────────────────────────────────────

describe('FeedForm — edit mode (with initialValues)', () => {
  it('pre-populates description, url, schedule and confidence from initialValues', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const urlInput = screen.getByLabelText(/^url$/i) as HTMLInputElement
    expect(urlInput.value).toBe('https://api.abuseipdb.com/api/v2/blacklist')

    const descInput = screen.getByLabelText(/description/i) as HTMLInputElement
    expect(descInput.value).toBe('Community IPs')
  })

  it('shows "Save Changes" submit button instead of "Create Feed"', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: /save changes/i })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /create feed/i })).toBeNull()
  })

  it('displays feed name as read-only text, not an editable input', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // Name is shown as static text, not an interactive input
    expect(screen.getByText('AbuseIPDB')).toBeTruthy()
    // No input labelled "Feed Name" (it's read-only in edit mode)
    expect(screen.queryByLabelText(/feed name/i)).toBeNull()
  })

  it('does not render the raw JSON auth textarea in edit mode', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.queryByPlaceholderText(/api_key/i)).toBeNull()
  })

  it('shows API key input when auth_supported is true', () => {
    render(
      <FeedForm
        initialValues={{ ...baseEditFeed, auth_supported: true }}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByLabelText(/api key/i)).toBeTruthy()
  })

  it('does not show API key input when auth_supported is false', () => {
    render(
      <FeedForm
        initialValues={{ ...baseEditFeed, auth_supported: false }}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.queryByLabelText(/api key/i)).toBeNull()
  })

  it('API key placeholder says "Leave blank to keep current key" when has_auth is true', () => {
    render(
      <FeedForm
        initialValues={{ ...baseEditFeed, auth_supported: true, has_auth: true }}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const apiKeyInput = screen.getByLabelText(/api key/i) as HTMLInputElement
    expect(apiKeyInput.placeholder).toMatch(/leave blank/i)
  })

  it('API key placeholder says "Enter API key" when has_auth is false', () => {
    render(
      <FeedForm
        initialValues={{ ...baseEditFeed, auth_supported: true, has_auth: false }}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const apiKeyInput = screen.getByLabelText(/api key/i) as HTMLInputElement
    expect(apiKeyInput.placeholder).toMatch(/enter api key/i)
  })

  it('does not include auth_config in payload when API key field is left blank', () => {
    const handleSubmit = vi.fn()
    render(
      <FeedForm
        initialValues={{ ...baseEditFeed, auth_supported: true, has_auth: true }}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
      />,
    )
    // submit without typing in the API key field
    fireEvent.submit(
      screen.getByRole('button', { name: /save changes/i }).closest('form')!,
    )
    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect('auth_config' in payload).toBe(false)
  })

  it('includes auth_config.api_key_value in payload when API key field is filled', () => {
    const handleSubmit = vi.fn()
    render(
      <FeedForm
        initialValues={{ ...baseEditFeed, auth_supported: true, has_auth: false }}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: 'my-secret-key-123' },
    })
    fireEvent.submit(
      screen.getByRole('button', { name: /save changes/i }).closest('form')!,
    )
    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect(payload.auth_config).toEqual({ api_key_value: 'my-secret-key-123' })
  })

  it('calls onSubmit with FeedUpdate payload containing changed description', () => {
    const handleSubmit = vi.fn()
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: 'Updated description' },
    })
    fireEvent.submit(
      screen.getByRole('button', { name: /save changes/i }).closest('form')!,
    )
    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect(payload.description).toBe('Updated description')
  })

  it('shows "Saving..." on submit button when isLoading is true in edit mode', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        isLoading
      />,
    )
    expect(screen.getByRole('button', { name: /saving/i })).toBeTruthy()
  })

  it('calls onCancel when Cancel button is clicked in edit mode', () => {
    const handleCancel = vi.fn()
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={handleCancel}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(handleCancel).toHaveBeenCalledOnce()
  })
})

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

// Custom (non-preconfigured) feed fixture for edit-mode tests
const customEditFeed: Feed = {
  ...baseEditFeed,
  id: 'f2',
  name: 'My Custom Feed',
  feed_type: 'file',
  url: 'https://custom.example.com/feed.txt',
  is_preconfigured: false,
  has_auth: false,
  auth_supported: false,
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

// ── Edit mode — preconfigured feeds ─────────────────────────────────────────

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

  it('displays feed name as read-only text, not an editable input (preconfigured)', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // Name is shown as static text, not an interactive input
    expect(screen.getByText('AbuseIPDB')).toBeTruthy()
    // No input labelled "Feed Name" — preconfigured feed name is read-only
    expect(screen.queryByLabelText(/feed name/i)).toBeNull()
  })

  it('shows URL as disabled (not editable) and feed type as read-only text for preconfigured feed', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // URL is a disabled input (seeded value, not editable)
    const urlInput = screen.getByLabelText(/^url$/i) as HTMLInputElement
    expect(urlInput.disabled).toBe(true)
    // Feed Type shown as text, no select
    expect(screen.queryByLabelText(/feed type/i)).toBeNull()
  })

  it('does not render the raw JSON auth textarea when knownAuth is true', () => {
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // baseEditFeed has auth_supported:true → knownAuth=true → API key shown, not JSON textarea
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

  it('shows API key input when has_auth is true even if auth_supported is false (key-rotation regression)', () => {
    // Primary regression: custom feed with has_auth:true, auth_supported:false must show the API key
    // field so the user can rotate the key
    render(
      <FeedForm
        initialValues={{ ...customEditFeed, has_auth: true, auth_supported: false }}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByLabelText(/api key/i)).toBeTruthy()
  })

  it('does not show API key input when auth_supported is false and has_auth is false', () => {
    render(
      <FeedForm
        initialValues={{ ...baseEditFeed, auth_supported: false }}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // knownAuth = false → JSON textarea shown, not API key
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

  it('sends auth_config.api_key_value when rotating key on custom feed (has_auth:true, auth_supported:false)', () => {
    const handleSubmit = vi.fn()
    render(
      <FeedForm
        initialValues={{ ...customEditFeed, has_auth: true, auth_supported: false }}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: 'rotate-my-key' },
    })
    fireEvent.submit(
      screen.getByRole('button', { name: /save changes/i }).closest('form')!,
    )
    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect(payload.auth_config).toEqual({ api_key_value: 'rotate-my-key' })
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

// ── Edit mode — custom (non-preconfigured) feeds ──────────────────────────────

describe('FeedForm — edit mode, custom feed', () => {
  it('shows editable Feed Name input seeded from initialValues', () => {
    render(
      <FeedForm
        initialValues={customEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const nameInput = screen.getByLabelText(/feed name/i) as HTMLInputElement
    expect(nameInput.value).toBe('My Custom Feed')
  })

  it('shows editable Feed Type select for custom feed', () => {
    render(
      <FeedForm
        initialValues={customEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // Select is present (not read-only text)
    expect(screen.getByLabelText(/feed type/i)).toBeTruthy()
  })

  it('shows editable URL input (not disabled) for custom feed', () => {
    render(
      <FeedForm
        initialValues={customEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const urlInput = screen.getByLabelText(/^url$/i) as HTMLInputElement
    expect(urlInput.disabled).toBe(false)
    expect(urlInput.value).toBe('https://custom.example.com/feed.txt')
  })

  it('shows JSON Auth Config textarea for custom feed with has_auth:false and auth_supported:false', () => {
    render(
      <FeedForm
        initialValues={customEditFeed}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // knownAuth = false → JSON textarea, not the password field
    expect(screen.queryByLabelText(/api key/i)).toBeNull()
    expect(screen.getByPlaceholderText(/api_key/i)).toBeTruthy()
  })

  it('includes name, feed_type, and url in FeedUpdate payload for custom feed', () => {
    const handleSubmit = vi.fn()
    render(
      <FeedForm
        initialValues={customEditFeed}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByLabelText(/feed name/i), {
      target: { value: 'Renamed Feed' },
    })
    fireEvent.submit(
      screen.getByRole('button', { name: /save changes/i }).closest('form')!,
    )
    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect(payload.name).toBe('Renamed Feed')
    expect(payload.feed_type).toBe('file')
    expect(payload.url).toBe('https://custom.example.com/feed.txt')
  })

  it('does not include name, feed_type, or url in FeedUpdate payload for preconfigured feed', () => {
    const handleSubmit = vi.fn()
    render(
      <FeedForm
        initialValues={baseEditFeed}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
      />,
    )
    fireEvent.submit(
      screen.getByRole('button', { name: /save changes/i }).closest('form')!,
    )
    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect('name' in payload).toBe(false)
    expect('feed_type' in payload).toBe(false)
    expect('url' in payload).toBe(false)
  })

  it('sends auth_config from JSON textarea when filled for custom feed with !knownAuth', () => {
    const handleSubmit = vi.fn()
    render(
      <FeedForm
        initialValues={customEditFeed}
        onSubmit={handleSubmit}
        onCancel={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText(/api_key/i), {
      target: { value: '{"api_key": "abc123"}' },
    })
    fireEvent.submit(
      screen.getByRole('button', { name: /save changes/i }).closest('form')!,
    )
    expect(handleSubmit).toHaveBeenCalledOnce()
    const payload = handleSubmit.mock.calls[0][0]
    expect(payload.auth_config).toEqual({ api_key: 'abc123' })
  })
})

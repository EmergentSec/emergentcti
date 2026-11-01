import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider, useToast } from './ToastContext'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function Trigger() {
  const { toast } = useToast()
  return <button onClick={() => toast('Observable added successfully', 'success')}>Fire</button>
}

describe('ToastProvider', () => {
  it('renders toasts in a polite live region with tokenized styles and a dismiss button', () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    )
    const region = screen.getByRole('region', { name: 'Notifications' })
    expect(region.getAttribute('aria-live')).toBe('polite')

    fireEvent.click(screen.getByText('Fire'))
    expect(region.textContent).toContain('Observable added successfully')
    // No raw palette classes on the mounted toast.
    expect(region.innerHTML).not.toMatch(/\b(?:bg|text|border)-(?:green|red|blue)-\d/)

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }))
    act(() => {
      vi.advanceTimersByTime(250)
    })
    expect(region.textContent).not.toContain('Observable added successfully')
  })

  it('auto-dismisses', () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    )
    fireEvent.click(screen.getByText('Fire'))
    act(() => {
      vi.advanceTimersByTime(4500)
    })
    expect(screen.queryByText('Observable added successfully')).toBeNull()
  })
})

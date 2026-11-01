import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { TlpDowngradeReasonDialog } from './TlpDowngradeReasonDialog'

describe('TlpDowngradeReasonDialog', () => {
  it('requires a reason before confirming', () => {
    const onConfirm = vi.fn()
    render(<TlpDowngradeReasonDialog open onClose={() => {}} onConfirm={onConfirm} />)
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.getByText(/Reason is required/)).toBeTruthy()
  })
})

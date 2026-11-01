import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ObservableForm } from './ObservableForm'

afterEach(cleanup)

function fillValue() {
  fireEvent.change(screen.getByLabelText('Value'), { target: { value: ' 1.2.3.4 ' } })
}

describe('ObservableForm manual TLP', () => {
  it('defaults to Unspecified and sends tlp: null', () => {
    const onSubmit = vi.fn()
    render(<ObservableForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    expect((screen.getByLabelText('TLP marking') as HTMLSelectElement).value).toBe('')
    fillValue()
    fireEvent.click(screen.getByRole('button', { name: 'Add Observable' }))
    expect(onSubmit).toHaveBeenCalledWith({
      type: 'ip-addr',
      value: '1.2.3.4',
      confidence_score: 75,
      tlp: null,
    })
  })

  it('sends the chosen marking as the `tlp` request field', () => {
    const onSubmit = vi.fn()
    render(<ObservableForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('TLP marking'), { target: { value: 'amber+strict' } })
    fillValue()
    fireEvent.click(screen.getByRole('button', { name: 'Add Observable' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ tlp: 'amber+strict' }))
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('manual_tlp')
  })
})

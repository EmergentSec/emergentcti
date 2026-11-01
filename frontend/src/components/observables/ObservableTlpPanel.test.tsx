import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ObservableTlpPanel } from './ObservableTlpPanel'
import { EMPTY_TLP_OBSERVABLE_FIELDS } from '@/test/fixtures/tlp'
import type { Observable } from '@/types/observable'

const mockSetTlp = vi.fn()
const mockClearTlp = vi.fn()

vi.mock('@/hooks/useObservables', () => ({
  useSetTlpOverride: () => ({ mutate: mockSetTlp, isPending: false }),
  useClearTlpOverride: () => ({ mutate: mockClearTlp, isPending: false }),
  useSetObservableTags: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ isAdmin: true }),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

const BASE: Observable = {
  id: 'obs-1',
  type: 'ip-addr',
  value: '1.2.3.4',
  confidence_score: 50,
  manual_confidence: null,
  confidence_override: null,
  first_seen: null,
  last_seen: null,
  source_count: 0,
  sources: [],
  allowlisted: false,
  allowlist_entry_ids: [],
  ...EMPTY_TLP_OBSERVABLE_FIELDS,
  effective_tlp: 'amber',
  tlp_sources: [{ kind: 'manual', id: null, name: 'Manual', tlp: 'amber' }],
  created_at: '',
  updated_at: '',
}

describe('ObservableTlpPanel', () => {
  it('lists why this marking sources', () => {
    render(
      <MemoryRouter>
        <ObservableTlpPanel observable={BASE} observableId="obs-1" />
      </MemoryRouter>,
    )
    expect(screen.getByText('Why this marking')).toBeTruthy()
    expect(screen.getAllByLabelText(/TLP:AMBER\./).length).toBeGreaterThan(0)
  })

  it('requires reason for admin override', () => {
    render(
      <MemoryRouter>
        <ObservableTlpPanel observable={BASE} observableId="obs-1" />
      </MemoryRouter>,
    )
    const form = document.getElementById('tlp-override-reason')?.closest('form')
    expect(form).toBeTruthy()
    fireEvent.submit(form!)
    expect(mockSetTlp).not.toHaveBeenCalled()
    expect(screen.getByText('Reason is required')).toBeTruthy()
  })
})

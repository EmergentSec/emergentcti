import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiUsagePanel } from './AiUsage'
import * as aiApi from '@/api/ai'
import { currentUtcMonth } from '@/lib/aiDisplay'
import {
  UNPRICED_TOTALS,
  byDay,
  byProviderModel,
  usageRecord,
  usageReport,
  usageTotals,
} from '@/test/fixtures/ai'

vi.mock('@/api/ai', () => ({
  getAiUsage: vi.fn(),
  getAiUsageRecords: vi.fn(),
}))

const api = vi.mocked(aiApi)
const NO_RECORDS = { items: [], next_before: null }

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AiUsagePanel />
    </QueryClientProvider>,
  )
}

async function panel() {
  return screen.findByRole('region', { name: 'AI usage' })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AiUsagePanel unknown cost and tokens (H1)', () => {
  it('never renders a bare $0 when every cost is unknown, in totals and every breakdown row', async () => {
    api.getAiUsage.mockResolvedValue(
      usageReport({
        totals: usageTotals(UNPRICED_TOTALS),
        budget: { monthly_budget_usd: null, committed_usd: '0.500000', remaining_usd: null },
        by_provider_model: [byProviderModel('anthropic', 'claude-unpriced', UNPRICED_TOTALS)],
        by_day: [byDay('2026-11-02', UNPRICED_TOTALS)],
      }),
    )
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()

    await within(section).findByText('No budget set')
    expect(section.textContent).not.toMatch(/\$0\.000000 est\./)
    // Totals + one provider/model row + one day row.
    expect(within(section).getAllByText('Unknown (1 request)')).toHaveLength(3)
    const byModel = within(section).getByRole('table', { name: 'By provider and model' })
    expect(within(byModel).getByText('Unknown (1 request)')).toBeTruthy()
    const days = within(section).getByRole('table', { name: 'By day' })
    expect(within(days).getByText('Unknown (1 request)')).toBeTruthy()
    expect(within(section).getByText(/1 request\(s\) with unknown cost/)).toBeTruthy()
  })

  it('shows known cost plus the unknown count when some costs are known', async () => {
    const mixed = { requests: 3, estimated_cost_usd: '0.000102', cost_unknown_requests: 2 }
    api.getAiUsage.mockResolvedValue(
      usageReport({
        totals: usageTotals(mixed),
        by_provider_model: [byProviderModel('openai', 'gpt-z', mixed)],
        by_day: [byDay('2026-11-02', mixed)],
      }),
    )
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()
    await waitFor(() => expect(within(section).getAllByText('$0.000102 est. + 2 unknown')).toHaveLength(3))
  })

  it('flags unknown token usage in totals and rows', async () => {
    const tokens = { requests: 2, input_tokens: 12, output_tokens: 1, token_unknown_requests: 1 }
    api.getAiUsage.mockResolvedValue(
      usageReport({
        totals: usageTotals(tokens),
        by_provider_model: [byProviderModel('anthropic', 'm', tokens)],
        by_day: [byDay('2026-11-02', { requests: 1, token_unknown_requests: 1 })],
      }),
    )
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()
    expect(await within(section).findAllByText('12 + 1 unknown')).toHaveLength(1)
    const byModel = within(section).getByRole('table', { name: 'By provider and model' })
    expect(within(byModel).getByText(/12 \+ 1 unknown \/ 1 \+ 1 unknown/)).toBeTruthy()
    const days = within(section).getByRole('table', { name: 'By day' })
    expect(within(days).getByText(/Unknown \(1 request\) \/ Unknown \(1 request\)/)).toBeTruthy()
    expect(within(section).getByText(/1 request\(s\) with unknown token usage/)).toBeTruthy()
  })

  it('shows plain estimates when nothing is unknown', async () => {
    api.getAiUsage.mockResolvedValue(
      usageReport({
        totals: usageTotals({ requests: 1, estimated_cost_usd: '2.500000', committed_usd: '2.500000' }),
        budget: { monthly_budget_usd: '10.0000', committed_usd: '2.500000', remaining_usd: '7.500000' },
      }),
    )
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()
    expect(await within(section).findByRole('meter', { name: 'Budget committed' })).toBeTruthy()
    expect(within(section).getAllByText(/\$2\.500000 est\./).length).toBeGreaterThan(0)
    expect(section.textContent).not.toMatch(/unknown/i)
  })
})

describe('AiUsagePanel budget meter (M6, L1)', () => {
  it('fills the meter and marks over budget when the budget is zero and spend exists', async () => {
    api.getAiUsage.mockResolvedValue(
      usageReport({
        totals: usageTotals({ requests: 1, committed_usd: '0.500000', estimated_cost_usd: '0.500000' }),
        budget: { monthly_budget_usd: '0.0000', committed_usd: '0.500000', remaining_usd: '-0.500000' },
      }),
    )
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()
    const meter = await within(section).findByRole('meter', { name: 'Budget committed' })
    expect(meter.getAttribute('aria-valuenow')).toBe('100')
    expect(meter.getAttribute('aria-valuetext')).toBe('$0.500000 est. of $0.0000 est. committed, over budget')
    expect(meter.querySelector('[data-over-budget="true"]')?.className).toMatch(/bg-destructive/)
    // L1: the over-budget amount keeps the backend's decimals (no float round-trip).
    expect(within(section).getByText('Over budget by $0.500000 est.')).toBeTruthy()
  })

  it('uses the normal tone under budget', async () => {
    api.getAiUsage.mockResolvedValue(
      usageReport({
        budget: { monthly_budget_usd: '10.0000', committed_usd: '2.500000', remaining_usd: '7.500000' },
      }),
    )
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const meter = await within(await panel()).findByRole('meter', { name: 'Budget committed' })
    expect(meter.getAttribute('aria-valuenow')).toBe('25')
    expect(meter.getAttribute('aria-valuetext')).not.toMatch(/over budget/)
    expect(meter.querySelector('[data-over-budget]')).toBeNull()
  })
})

describe('AiUsagePanel month picker and period copy (M2, L5)', () => {
  it('ignores a cleared or malformed month: no empty month is ever requested', async () => {
    api.getAiUsage.mockResolvedValue(usageReport())
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()
    const input = within(section).getByLabelText('Month (UTC)')
    await within(section).findByText(/November 2026, UTC calendar month\./)

    fireEvent.change(input, { target: { value: '' } })
    expect(await within(section).findByText(/Enter a month as YYYY-MM/)).toBeTruthy()
    expect(input.getAttribute('aria-invalid')).toBe('true')

    for (const call of [...api.getAiUsage.mock.calls, ...api.getAiUsageRecords.mock.calls]) {
      expect(call[0]).toBe(currentUtcMonth())
    }
    // The period line still describes the last valid month.
    expect(within(section).getByText(/November 2026, UTC calendar month\./)).toBeTruthy()
  })

  it('requests a newly picked valid month', async () => {
    api.getAiUsage.mockResolvedValue(usageReport())
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()
    fireEvent.change(within(section).getByLabelText('Month (UTC)'), { target: { value: '2026-10' } })
    await waitFor(() => expect(api.getAiUsage).toHaveBeenCalledWith('2026-10'))
    expect(api.getAiUsageRecords).toHaveBeenCalledWith('2026-10', 50, undefined)
  })

  it('builds the period line from the response, including actions in scope', async () => {
    api.getAiUsage.mockResolvedValue(
      usageReport({
        period: { month: '2026-09', start: '2026-09-01T00:00:00Z', end: '2026-10-01T00:00:00Z', timezone: 'UTC' },
        actions_in_scope: ['inference_test', 'report_summary'],
      }),
    )
    api.getAiUsageRecords.mockResolvedValue(NO_RECORDS)
    renderPanel()
    const section = await panel()
    expect(
      await within(section).findByText(
        'September 2026, UTC calendar month. In scope: connection inference tests, report_summary.',
      ),
    ).toBeTruthy()
  })
})

describe('AiUsagePanel records (L2, H2)', () => {
  it('renders UTC times, actor, reserved holds, non-billed rows, nulls and errors', async () => {
    api.getAiUsage.mockResolvedValue(usageReport())
    api.getAiUsageRecords.mockResolvedValue({
      items: [
        usageRecord({ id: 'a' }),
        usageRecord({
          id: 'b',
          actor_label: null,
          status: 'reserved',
          stale: true,
          billable: 'unknown',
          completed_at: null,
          latency_ms: null,
          input_tokens: null,
          output_tokens: null,
          usage_source: 'unknown',
          reserved_usd: '0.015360',
          cost_usd: null,
          cost_source: 'unknown',
        }),
        usageRecord({
          id: 'c',
          status: 'failed',
          billable: 'no',
          input_tokens: null,
          output_tokens: null,
          usage_source: 'unknown',
          cost_usd: null,
          cost_source: 'unknown',
          error_category: 'invalid_credentials',
          retry_of: 'a',
        }),
        usageRecord({
          id: 'd',
          status: 'failed',
          billable: 'unknown',
          cost_usd: null,
          cost_source: 'unknown',
          error_category: 'something_new',
        }),
      ],
      next_before: null,
    })
    renderPanel()
    const table = await within(await panel()).findByRole('table', { name: 'Recent records' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(4)

    expect(within(rows[0]).getByText('2026-11-02 14:05 UTC')).toBeTruthy()
    expect(within(rows[0]).getByText('admin')).toBeTruthy()
    expect(within(rows[0]).getByText('$0.000051 est.')).toBeTruthy()

    expect(within(rows[1]).getByText('Unknown')).toBeTruthy() // null actor_label
    expect(within(rows[1]).getByText('reserved (stale)')).toBeTruthy()
    expect(within(rows[1]).getByText('Reserved $0.015360 est.')).toBeTruthy()
    expect(rows[1].textContent).toMatch(/Unknown \/ Unknown \(Unknown\)/)

    expect(within(rows[2]).getByText('Not billed')).toBeTruthy()
    expect(within(rows[2]).getByText('Retry')).toBeTruthy()
    expect(within(rows[2]).getByText(/rejected this API key/)).toBeTruthy()

    expect(within(rows[3]).getByText(/^Unknown/)).toBeTruthy()
    expect(within(rows[3]).getByText('Something went wrong talking to the provider.')).toBeTruthy()
  })

  it('pages with the next_before cursor', async () => {
    api.getAiUsage.mockResolvedValue(usageReport())
    api.getAiUsageRecords
      .mockResolvedValueOnce({ items: [usageRecord({ id: 'first', model: 'model-one' })], next_before: 'first' })
      .mockResolvedValueOnce({ items: [usageRecord({ id: 'second', model: 'model-two' })], next_before: null })
    renderPanel()
    const section = await panel()
    fireEvent.click(await within(section).findByRole('button', { name: 'Load more records' }))
    expect(await within(section).findByText('anthropic/model-two')).toBeTruthy()
    expect(within(section).getByText('anthropic/model-one')).toBeTruthy()
    expect(api.getAiUsageRecords).toHaveBeenLastCalledWith(currentUtcMonth(), 50, 'first')
    expect(within(section).queryByRole('button', { name: 'Load more records' })).toBeNull()
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import api from './client'
import { createReport, extractReportIndicators, importReportIndicators, updateReport } from './reports'
import type { ExtractionPreview, ImportResult } from '@/types/reportIocExtraction'

afterEach(() => vi.restoreAllMocks())

const PREVIEW: ExtractionPreview = {
  report_id: 'rep-1',
  sources: [],
  candidates: [],
  truncated: false,
  counts: { total: 0, new: 0, existing: 0, invalid: 0 },
}

const RESULT: ImportResult = {
  created: 1,
  attributed_existing: 0,
  already_attributed: 0,
  observables: [],
}

describe('report indicator extraction API', () => {
  it('POSTs to extract and import routes with contract payloads', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: PREVIEW }).mockResolvedValueOnce({ data: RESULT })

    await extractReportIndicators('rep-1')
    expect(post).toHaveBeenNthCalledWith(1, '/reports/rep-1/extract')

    await importReportIndicators('rep-1', {
      confidence: 50,
      items: [{ type: 'ip-addr', value: '1.2.3.4' }],
    })
    expect(post).toHaveBeenNthCalledWith(2, '/reports/rep-1/import', {
      confidence: 50,
      items: [{ type: 'ip-addr', value: '1.2.3.4' }],
    })
  })
})

describe('report create/update with tags', () => {
  const DETAIL = { id: 'rep-1', tags: [] as string[] }

  it('omits tags from POST (backend ignores them) and saves them via PUT /reports/{id}/tags', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: DETAIL })
    const put = vi
      .spyOn(api, 'put')
      .mockResolvedValue({ data: { ...DETAIL, tags: ['apt'] } })

    const result = await createReport({ title: 'T', origin: 'internal', tlp: 'amber', tags: ['apt'] })

    expect(post).toHaveBeenCalledWith('/reports', { title: 'T', origin: 'internal', tlp: 'amber' })
    expect(put).toHaveBeenCalledWith('/reports/rep-1/tags', { tags: ['apt'] })
    expect(result.tags).toEqual(['apt'])
  })

  it('does not PUT tags on create when none were chosen', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: DETAIL })
    const put = vi.spyOn(api, 'put')
    await createReport({ title: 'T', origin: 'internal', tags: [] })
    expect(put).not.toHaveBeenCalled()
  })

  it('omits tags from PATCH and replaces them via PUT when provided', async () => {
    const patch = vi.spyOn(api, 'patch').mockResolvedValue({ data: DETAIL })
    const put = vi.spyOn(api, 'put').mockResolvedValue({ data: DETAIL })

    await updateReport('rep-1', { tlp: null, tlp_change_reason: 'public now', tags: [] })

    expect(patch).toHaveBeenCalledWith('/reports/rep-1', { tlp: null, tlp_change_reason: 'public now' })
    expect(put).toHaveBeenCalledWith('/reports/rep-1/tags', { tags: [] })
  })

  it('does not PUT tags on update when tags were not sent (non-admin)', async () => {
    vi.spyOn(api, 'patch').mockResolvedValue({ data: DETAIL })
    const put = vi.spyOn(api, 'put')
    await updateReport('rep-1', { title: 'New' })
    expect(put).not.toHaveBeenCalled()
  })
})

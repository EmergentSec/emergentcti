import { afterEach, describe, expect, it, vi } from 'vitest'
import api from './client'
import { extractReportIndicators, importReportIndicators } from './reports'
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

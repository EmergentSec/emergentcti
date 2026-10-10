import { afterEach, describe, expect, it, vi } from 'vitest'
import api from './client'
import { createAllowlistEntry, deleteAllowlistEntry, getAllowlist } from './allowlist'
import {
  createExportProfile,
  deleteExportProfile,
  exportProfileDownloadPath,
  exportProfileDownloadUrl,
  getExportProfilePreview,
  getExportProfiles,
  updateExportProfile,
} from './exportProfiles'

const PROFILE_INPUT = {
  name: 'Firewall',
  description: null,
  format: 'text' as const,
  type: 'ip-addr' as const,
  confidence_min: 70,
  max_age_days: null,
  feed_id: null,
}

afterEach(() => vi.restoreAllMocks())

describe('export profile download URLs', () => {
  it('builds the relative download path', () => {
    expect(exportProfileDownloadPath('p-1')).toBe('/api/v1/export/profiles/p-1/download')
  })

  it('builds an absolute URL from the given origin without credentials', () => {
    expect(exportProfileDownloadUrl('p-1', 'https://cti.example.org')).toBe(
      'https://cti.example.org/api/v1/export/profiles/p-1/download',
    )
    expect(exportProfileDownloadUrl('p-1', 'https://cti.example.org/')).toBe(
      'https://cti.example.org/api/v1/export/profiles/p-1/download',
    )
  })

  it('defaults to the current window origin', () => {
    expect(exportProfileDownloadUrl('p-1')).toBe(
      `${window.location.origin}/api/v1/export/profiles/p-1/download`,
    )
  })
})

describe('export profile API', () => {
  it('uses the shared contract routes', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: [] })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })
    const put = vi.spyOn(api, 'put').mockResolvedValue({ data: {} })
    const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: undefined })

    await getExportProfiles()
    expect(get).toHaveBeenCalledWith('/export/profiles')

    await createExportProfile(PROFILE_INPUT)
    expect(post).toHaveBeenCalledWith('/export/profiles', PROFILE_INPUT)

    await updateExportProfile('p-1', PROFILE_INPUT)
    expect(put).toHaveBeenCalledWith('/export/profiles/p-1', PROFILE_INPUT)

    await deleteExportProfile('p-1')
    expect(del).toHaveBeenCalledWith('/export/profiles/p-1')
  })

  it('returns the preview payload', async () => {
    const preview = { count: 3, excluded_allowlisted: 1, sample: ['1.1.1.1'] }
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: preview })
    await expect(getExportProfilePreview('p-1')).resolves.toEqual(preview)
    expect(get).toHaveBeenCalledWith('/export/profiles/p-1/preview')
  })
})

describe('allowlist API', () => {
  it('uses the shared contract routes', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: [] })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })
    const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: undefined })
    const payload = { kind: 'cidr' as const, value: '10.0.0.0/8', observable_type: 'ip-addr' as const, reason: 'RFC1918' }

    await getAllowlist()
    expect(get).toHaveBeenCalledWith('/allowlist')

    await createAllowlistEntry(payload)
    expect(post).toHaveBeenCalledWith('/allowlist', payload)

    await deleteAllowlistEntry('al-1')
    expect(del).toHaveBeenCalledWith('/allowlist/al-1')
  })
})

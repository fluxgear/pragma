import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { deleteMediaAsset, fetchMediaContentBlob, listMediaAssets, uploadMediaAsset } from '@/api/media'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  getApiBase: vi.fn(() => '/api/v1'),
}))

const errorMocks = vi.hoisted(() => ({
  toApiClientError: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)
vi.mock('@/api/errors', () => errorMocks)

const accessToken = 'token-123'

describe('media API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('passes the bearer token when listing media assets', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    await listMediaAssets({
      mime_type: 'image/png',
      limit: 25,
      offset: 25,
      order_by: 'created_at',
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith(
      '/media/assets?mime_type=image%2Fpng&limit=25&offset=25&order_by=created_at',
      {
        accessToken,
      },
    )
  })

  it('omits query params when listing without filters', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    await listMediaAssets()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/media/assets', {
      accessToken,
    })
  })

  it('uploads raw file bodies with metadata in the query string', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'media-1' })
    const file = new File(['png'], 'hero.png', { type: 'image/png' })

    await uploadMediaAsset(file, {
      alt_text: 'Hero image',
      caption: 'Homepage hero',
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith(
      '/media/assets?filename=hero.png&alt_text=Hero+image&caption=Homepage+hero',
      {
        accessToken,
        method: 'POST',
        headers: {
          'Content-Type': 'image/png',
        },
        body: file,
      },
    )
  })

  it('passes the bearer token when deleting media assets', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(undefined)

    await deleteMediaAsset('media-1')

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/media/assets/media-1', {
      accessToken,
      method: 'DELETE',
    })
  })

  it('fetches authenticated media blobs for previews', async () => {
    const blob = new Blob(['png'], { type: 'image/png' })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(blob),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchMediaContentBlob('media-1')

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/media/assets/media-1/content', {
      credentials: 'include',
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })
    expect(result).toBe(blob)
  })

  it('fails fast when no session access token is available', () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    expect(() => listMediaAssets()).toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

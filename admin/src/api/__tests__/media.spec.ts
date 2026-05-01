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

  it('uploads raw file bodies with ASCII-safe encoded metadata headers', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'media-1' })
    const file = new File(['png'], 'héro\nimage.png', { type: 'image/png' })

    await uploadMediaAsset(file, {
      alt_text: 'Hero ☕\nimage',
      caption: 'Homepage “hero”',
      description: 'Line 1\r\nLine 2',
    })

    const requestOptions = apiClientMocks.apiRequest.mock.calls[0]?.[1]
    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/media/assets', {
      accessToken,
      method: 'POST',
      headers: {
        'Content-Type': 'image/png',
        'X-Pragma-Media-Filename': 'utf8-url:h%C3%A9ro%0Aimage.png',
        'X-Pragma-Media-Alt-Text': 'utf8-url:Hero%20%E2%98%95%0Aimage',
        'X-Pragma-Media-Caption': 'utf8-url:Homepage%20%E2%80%9Chero%E2%80%9D',
        'X-Pragma-Media-Description': 'utf8-url:Line%201%0D%0ALine%202',
      },
      body: file,
    })
    expect(() => new Headers(requestOptions.headers)).not.toThrow()
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

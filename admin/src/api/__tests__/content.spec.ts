import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createContentEntry, listContentEntries, listContentTypes, updateContentEntry } from '@/api/content'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

describe('content API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('passes the bearer token when listing content types', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    await listContentTypes()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/types', {
      accessToken,
    })
  })

  it('propagates pagination parameters when listing content types', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      items: [],
      total: 0,
      limit: 25,
      offset: 50,
    })

    await listContentTypes({
      limit: 25,
      offset: 50,
      order_by: 'name',
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith(
      '/content/types?limit=25&offset=50&order_by=name',
      {
        accessToken,
      },
    )
  })

  it('passes the bearer token when listing content entries', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    await listContentEntries({
      content_type_id: 'type-1',
      status: 'draft',
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith(
      '/content/entries?content_type_id=type-1&status=draft',
      {
        accessToken,
      },
    )
  })

  it('propagates filters and pagination parameters when listing content entries', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      items: [],
      total: 0,
      limit: 25,
      offset: 25,
    })

    await listContentEntries({
      content_type_slug: 'articles',
      status: 'published',
      limit: 25,
      offset: 25,
      order_by: 'published_at',
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith(
      '/content/entries?content_type_slug=articles&status=published&limit=25&offset=25&order_by=published_at',
      {
        accessToken,
      },
    )
  })

  it('passes the bearer token when creating a content entry', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'entry-1' })

    await createContentEntry({
      content_type_id: 'type-1',
      slug: null,
      status: 'draft',
      payload: {
        title: 'Hello',
      },
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/entries', {
      accessToken,
      method: 'POST',
      body: {
        content_type_id: 'type-1',
        slug: null,
        status: 'draft',
        payload: {
          title: 'Hello',
        },
      },
    })
  })

  it('passes the bearer token when updating a content entry', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'entry-1' })

    await updateContentEntry('entry-1', {
      slug: 'hello',
      status: 'published',
      payload: {
        title: 'Hello',
      },
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/entries/entry-1', {
      accessToken,
      method: 'PUT',
      body: {
        slug: 'hello',
        status: 'published',
        payload: {
          title: 'Hello',
        },
      },
    })
  })

  it('fails fast when no session access token is available', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    await expect(listContentTypes()).rejects.toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

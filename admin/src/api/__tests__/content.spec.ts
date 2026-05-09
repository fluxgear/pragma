import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  createContentEntry,
  createContentEntryPreview,
  createContentType,
  deleteContentType,
  getContentType,
  listContentEntries,
  listContentEntryRevisions,
  listContentTypes,
  publishContentEntry,
  restoreContentEntryRevision,
  unpublishContentEntry,
  updateContentEntry,
  updateContentType,
} from '@/api/content'
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

  it('passes the bearer token when getting a content type', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'type-1' })

    await getContentType('type-1')

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/types/type-1', {
      accessToken,
    })
  })

  it('sends create content type payloads without server-derived fields', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'type-1' })

    await createContentType({
      name: 'Article',
      slug: 'articles',
      description: 'Editorial articles',
      field_definitions: [
        {
          kind: 'text',
          name: 'title',
          label: 'Title',
          required: true,
          help_text: 'Shown in listings.',
          default_value: 'Untitled',
          max_length: 120,
        },
      ],
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/types', {
      accessToken,
      method: 'POST',
      body: {
        name: 'Article',
        slug: 'articles',
        description: 'Editorial articles',
        field_definitions: [
          {
            kind: 'text',
            name: 'title',
            label: 'Title',
            required: true,
            help_text: 'Shown in listings.',
            default_value: 'Untitled',
            max_length: 120,
          },
        ],
      },
    })
  })

  it('sends update content type payloads to the detail endpoint', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'type-1' })

    await updateContentType('type-1', {
      name: 'Article',
      slug: null,
      description: null,
      field_definitions: [
        {
          kind: 'boolean',
          name: 'featured',
          label: 'Featured',
          required: false,
          default_value: false,
        },
      ],
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/types/type-1', {
      accessToken,
      method: 'PUT',
      body: {
        name: 'Article',
        slug: null,
        description: null,
        field_definitions: [
          {
            kind: 'boolean',
            name: 'featured',
            label: 'Featured',
            required: false,
            default_value: false,
          },
        ],
      },
    })
  })

  it('deletes content types through the backend detail endpoint', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(undefined)

    await deleteContentType('type-1')

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/types/type-1', {
      accessToken,
      method: 'DELETE',
    })
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

  it('sends workflow update payloads with SEO metadata and version guard', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'entry-1' })

    await updateContentEntry('entry-1', {
      slug: 'hello',
      status: 'draft',
      payload: {
        title: 'Hello',
      },
      seo_metadata: {
        title: 'Search title',
        description: 'Search description',
        canonical_url: '/hello',
        robots: 'index',
        og_title: 'Social title',
        og_description: 'Social description',
        og_image: '/media/hero.png',
      },
      expected_version: 4,
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/content/entries/entry-1', {
      accessToken,
      method: 'PUT',
      body: {
        slug: 'hello',
        status: 'draft',
        payload: {
          title: 'Hello',
        },
        seo_metadata: {
          title: 'Search title',
          description: 'Search description',
          canonical_url: '/hello',
          robots: 'index',
          og_title: 'Social title',
          og_description: 'Social description',
          og_image: '/media/hero.png',
        },
        expected_version: 4,
      },
    })
  })

  it('calls content workflow revision and preview endpoints', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ items: [] })

    await listContentEntryRevisions('entry-1')

    expect(apiClientMocks.apiRequest).toHaveBeenLastCalledWith(
      '/content/entries/entry-1/revisions',
      {
        accessToken,
      },
    )

    apiClientMocks.apiRequest.mockResolvedValue({
      entry_id: 'entry-1',
      token: 'signed-preview-token',
      preview_url: '/preview/content/signed-preview-token',
      expires_at: '2026-05-07T12:15:00Z',
    })

    await createContentEntryPreview('entry-1')

    expect(apiClientMocks.apiRequest).toHaveBeenLastCalledWith(
      '/content/entries/entry-1/preview',
      {
        accessToken,
        method: 'POST',
      },
    )
  })

  it('calls publish, unpublish, and restore endpoints with expected version payloads', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'entry-1' })

    await publishContentEntry('entry-1', { expected_version: 5 })
    await unpublishContentEntry('entry-1', { expected_version: 6 })
    await restoreContentEntryRevision('entry-1', 'revision-2', { expected_version: 7 })

    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(1, '/content/entries/entry-1/publish', {
      accessToken,
      method: 'POST',
      body: { expected_version: 5 },
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(2, '/content/entries/entry-1/unpublish', {
      accessToken,
      method: 'POST',
      body: { expected_version: 6 },
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(
      3,
      '/content/entries/entry-1/revisions/revision-2/restore',
      {
        accessToken,
        method: 'POST',
        body: { expected_version: 7 },
      },
    )
  })

  it('fails fast when no session access token is available', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    await expect(listContentTypes()).rejects.toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

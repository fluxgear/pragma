import { authenticatedApiRequest } from '@/api/authenticated'
import type {
  ContentEntryCreateRequest,
  ContentEntryListResponse,
  ContentEntryPreviewResponse,
  ContentEntryResponse,
  ContentEntryRevisionListResponse,
  ContentEntryRevisionRestoreRequest,
  ContentEntryStatus,
  ContentEntryTransitionRequest,
  ContentEntryUpdateRequest,
  ContentTypeCreateRequest,
  ContentTypeListResponse,
  ContentTypeResponse,
  ContentTypeUpdateRequest,
} from '@/api/types'

export type ContentTypeOrderBy = 'created_at' | 'updated_at' | 'name' | 'slug'
export type ContentEntryOrderBy = 'created_at' | 'updated_at' | 'published_at' | 'slug'

export interface ListContentTypesParams {
  limit?: number
  offset?: number
  order_by?: ContentTypeOrderBy
}

export interface ListContentEntriesParams {
  content_type_id?: string
  content_type_slug?: string
  status?: ContentEntryStatus
  limit?: number
  offset?: number
  order_by?: ContentEntryOrderBy
}

function appendPaginationParams(
  searchParams: URLSearchParams,
  params: { limit?: number; offset?: number; order_by?: string },
): void {
  if (params.limit !== undefined) {
    searchParams.set('limit', String(params.limit))
  }

  if (params.offset !== undefined) {
    searchParams.set('offset', String(params.offset))
  }

  if (params.order_by) {
    searchParams.set('order_by', params.order_by)
  }
}

function buildContentTypeQuery(params: ListContentTypesParams = {}): string {
  const searchParams = new URLSearchParams()
  appendPaginationParams(searchParams, params)

  const query = searchParams.toString()
  return query.length > 0 ? `/content/types?${query}` : '/content/types'
}

function buildEntryQuery(params: ListContentEntriesParams = {}): string {
  const searchParams = new URLSearchParams()

  if (params.content_type_id) {
    searchParams.set('content_type_id', params.content_type_id)
  }

  if (params.content_type_slug) {
    searchParams.set('content_type_slug', params.content_type_slug)
  }

  if (params.status) {
    searchParams.set('status', params.status)
  }

  appendPaginationParams(searchParams, params)

  const query = searchParams.toString()
  return query.length > 0 ? `/content/entries?${query}` : '/content/entries'
}

export function listContentTypes(
  params: ListContentTypesParams = {},
): Promise<ContentTypeListResponse> {
  return authenticatedApiRequest<ContentTypeListResponse>(buildContentTypeQuery(params))
}

export function getContentType(contentTypeId: string): Promise<ContentTypeResponse> {
  return authenticatedApiRequest<ContentTypeResponse>(`/content/types/${contentTypeId}`)
}

export function createContentType(
  payload: ContentTypeCreateRequest,
): Promise<ContentTypeResponse> {
  return authenticatedApiRequest<ContentTypeResponse>('/content/types', {
    method: 'POST',
    body: payload,
  })
}

export function updateContentType(
  contentTypeId: string,
  payload: ContentTypeUpdateRequest,
): Promise<ContentTypeResponse> {
  return authenticatedApiRequest<ContentTypeResponse>(`/content/types/${contentTypeId}`, {
    method: 'PUT',
    body: payload,
  })
}

export function deleteContentType(contentTypeId: string): Promise<void> {
  return authenticatedApiRequest<void>(`/content/types/${contentTypeId}`, {
    method: 'DELETE',
  })
}

export function listContentEntries(
  params: ListContentEntriesParams = {},
): Promise<ContentEntryListResponse> {
  return authenticatedApiRequest<ContentEntryListResponse>(buildEntryQuery(params))
}

export function createContentEntry(
  payload: ContentEntryCreateRequest,
): Promise<ContentEntryResponse> {
  return authenticatedApiRequest<ContentEntryResponse>('/content/entries', {
    method: 'POST',
    body: payload,
  })
}

export function updateContentEntry(
  entryId: string,
  payload: ContentEntryUpdateRequest,
): Promise<ContentEntryResponse> {
  return authenticatedApiRequest<ContentEntryResponse>(`/content/entries/${entryId}`, {
    method: 'PUT',
    body: payload,
  })
}

export function listContentEntryRevisions(
  entryId: string,
): Promise<ContentEntryRevisionListResponse> {
  return authenticatedApiRequest<ContentEntryRevisionListResponse>(
    `/content/entries/${entryId}/revisions`,
  )
}

export function createContentEntryPreview(
  entryId: string,
): Promise<ContentEntryPreviewResponse> {
  return authenticatedApiRequest<ContentEntryPreviewResponse>(
    `/content/entries/${entryId}/preview`,
    {
      method: 'POST',
    },
  )
}

export function publishContentEntry(
  entryId: string,
  payload: ContentEntryTransitionRequest = {},
): Promise<ContentEntryResponse> {
  return authenticatedApiRequest<ContentEntryResponse>(`/content/entries/${entryId}/publish`, {
    method: 'POST',
    body: payload,
  })
}

export function unpublishContentEntry(
  entryId: string,
  payload: ContentEntryTransitionRequest = {},
): Promise<ContentEntryResponse> {
  return authenticatedApiRequest<ContentEntryResponse>(`/content/entries/${entryId}/unpublish`, {
    method: 'POST',
    body: payload,
  })
}

export function restoreContentEntryRevision(
  entryId: string,
  revisionId: string,
  payload: ContentEntryRevisionRestoreRequest = {},
): Promise<ContentEntryResponse> {
  return authenticatedApiRequest<ContentEntryResponse>(
    `/content/entries/${entryId}/revisions/${revisionId}/restore`,
    {
      method: 'POST',
      body: payload,
    },
  )
}

import { apiRequest } from '@/api/client'
import type {
  ContentEntryCreateRequest,
  ContentEntryListResponse,
  ContentEntryResponse,
  ContentEntryStatus,
  ContentEntryUpdateRequest,
  ContentTypeListResponse,
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

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

function getAccessToken(): string {
  const authStore = useAuthStore()
  if (authStore.accessToken === null) {
    throw new Error('Authentication required')
  }
  return authStore.accessToken
}

export function listContentTypes(
  params: ListContentTypesParams = {},
): Promise<ContentTypeListResponse> {
  return apiRequest<ContentTypeListResponse>(buildContentTypeQuery(params), {
    accessToken: getAccessToken(),
  })
}

export function listContentEntries(
  params: ListContentEntriesParams = {},
): Promise<ContentEntryListResponse> {
  return apiRequest<ContentEntryListResponse>(buildEntryQuery(params), {
    accessToken: getAccessToken(),
  })
}

export function createContentEntry(
  payload: ContentEntryCreateRequest,
): Promise<ContentEntryResponse> {
  return apiRequest<ContentEntryResponse>('/content/entries', {
    accessToken: getAccessToken(),
    method: 'POST',
    body: payload,
  })
}

export function updateContentEntry(
  entryId: string,
  payload: ContentEntryUpdateRequest,
): Promise<ContentEntryResponse> {
  return apiRequest<ContentEntryResponse>(`/content/entries/${entryId}`, {
    accessToken: getAccessToken(),
    method: 'PUT',
    body: payload,
  })
}

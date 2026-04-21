import { apiRequest } from '@/api/client'
import type {
  ContentEntryCreateRequest,
  ContentEntryListResponse,
  ContentEntryResponse,
  ContentEntryStatus,
  ContentEntryUpdateRequest,
  ContentTypeListResponse,
} from '@/api/types'

export interface ListContentEntriesParams {
  content_type_id?: string
  status?: ContentEntryStatus
}

function buildEntryQuery(params: ListContentEntriesParams = {}): string {
  const searchParams = new URLSearchParams()

  if (params.content_type_id) {
    searchParams.set('content_type_id', params.content_type_id)
  }

  if (params.status) {
    searchParams.set('status', params.status)
  }

  const query = searchParams.toString()
  return query.length > 0 ? `/content/entries?${query}` : '/content/entries'
}

export function listContentTypes(): Promise<ContentTypeListResponse> {
  return apiRequest<ContentTypeListResponse>('/content/types')
}

export function listContentEntries(
  params: ListContentEntriesParams = {},
): Promise<ContentEntryListResponse> {
  return apiRequest<ContentEntryListResponse>(buildEntryQuery(params))
}

export function createContentEntry(
  payload: ContentEntryCreateRequest,
): Promise<ContentEntryResponse> {
  return apiRequest<ContentEntryResponse>('/content/entries', {
    method: 'POST',
    body: payload,
  })
}

export function updateContentEntry(
  entryId: string,
  payload: ContentEntryUpdateRequest,
): Promise<ContentEntryResponse> {
  return apiRequest<ContentEntryResponse>(`/content/entries/${entryId}`, {
    method: 'PUT',
    body: payload,
  })
}

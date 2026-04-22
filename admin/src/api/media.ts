import { apiRequest, getApiBase } from '@/api/client'
import { toApiClientError } from '@/api/errors'
import type { MediaAssetListResponse, MediaAssetResponse } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

export interface ListMediaAssetsParams {
  mime_type?: string
}

export interface UploadMediaAssetOptions {
  alt_text?: string | null
  caption?: string | null
  description?: string | null
}

function getAccessToken(): string {
  const authStore = useAuthStore()
  if (authStore.accessToken === null) {
    throw new Error('Authentication required')
  }
  return authStore.accessToken
}

function buildMediaListQuery(params: ListMediaAssetsParams = {}): string {
  const searchParams = new URLSearchParams()

  if (params.mime_type) {
    searchParams.set('mime_type', params.mime_type)
  }

  const query = searchParams.toString()
  return query.length > 0 ? `/media/assets?${query}` : '/media/assets'
}

function buildUploadPath(file: File, options: UploadMediaAssetOptions): string {
  const searchParams = new URLSearchParams({
    filename: file.name,
  })

  if (options.alt_text) {
    searchParams.set('alt_text', options.alt_text)
  }
  if (options.caption) {
    searchParams.set('caption', options.caption)
  }
  if (options.description) {
    searchParams.set('description', options.description)
  }

  return `/media/assets?${searchParams.toString()}`
}

export function listMediaAssets(
  params: ListMediaAssetsParams = {},
): Promise<MediaAssetListResponse> {
  return apiRequest<MediaAssetListResponse>(buildMediaListQuery(params), {
    accessToken: getAccessToken(),
  })
}

export function getMediaAsset(mediaId: string): Promise<MediaAssetResponse> {
  return apiRequest<MediaAssetResponse>(`/media/assets/${mediaId}`, {
    accessToken: getAccessToken(),
  })
}

export function uploadMediaAsset(
  file: File,
  options: UploadMediaAssetOptions = {},
): Promise<MediaAssetResponse> {
  return apiRequest<MediaAssetResponse>(buildUploadPath(file, options), {
    accessToken: getAccessToken(),
    method: 'POST',
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
    },
    body: file,
  })
}

export function deleteMediaAsset(mediaId: string): Promise<void> {
  return apiRequest<void>(`/media/assets/${mediaId}`, {
    accessToken: getAccessToken(),
    method: 'DELETE',
  })
}

export async function fetchMediaContentBlob(mediaId: string): Promise<Blob> {
  const response = await fetch(`${getApiBase()}/media/assets/${mediaId}/content`, {
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  })

  if (!response.ok) {
    throw await toApiClientError(response)
  }

  return await response.blob()
}

import { apiRequest, getApiBase } from '@/api/client'
import { toApiClientError } from '@/api/errors'
import type { MediaAssetListResponse, MediaAssetResponse } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

export interface ListMediaAssetsParams {
  mime_type?: string
  limit?: number
  offset?: number
  order_by?: 'created_at' | 'updated_at' | 'original_filename' | 'size_bytes'
}

export interface UploadMediaAssetOptions {
  alt_text?: string | null
  caption?: string | null
  description?: string | null
}

const UPLOAD_METADATA_HEADER_ENCODING_PREFIX = 'utf8-url:'

function encodeUploadMetadataHeaderValue(value: string): string {
  return UPLOAD_METADATA_HEADER_ENCODING_PREFIX + encodeURIComponent(value)
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

  if (params.limit !== undefined) {
    searchParams.set('limit', String(params.limit))
  }

  if (params.offset !== undefined) {
    searchParams.set('offset', String(params.offset))
  }

  if (params.order_by) {
    searchParams.set('order_by', params.order_by)
  }

  const query = searchParams.toString()
  return query.length > 0 ? '/media/assets?' + query : '/media/assets'
}

function buildUploadHeaders(file: File, options: UploadMediaAssetOptions): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': file.type || 'application/octet-stream',
    'X-Pragma-Media-Filename': encodeUploadMetadataHeaderValue(file.name),
  }

  if (options.alt_text) {
    headers['X-Pragma-Media-Alt-Text'] = encodeUploadMetadataHeaderValue(options.alt_text)
  }
  if (options.caption) {
    headers['X-Pragma-Media-Caption'] = encodeUploadMetadataHeaderValue(options.caption)
  }
  if (options.description) {
    headers['X-Pragma-Media-Description'] = encodeUploadMetadataHeaderValue(options.description)
  }

  return headers
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
  return apiRequest<MediaAssetResponse>('/media/assets', {
    accessToken: getAccessToken(),
    method: 'POST',
    headers: buildUploadHeaders(file, options),
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

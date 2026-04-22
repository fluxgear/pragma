import { toApiClientError } from '@/api/errors'

const apiBase = (import.meta.env.VITE_API_BASE ?? '/api/v1').replace(/\/$/, '')

export interface ApiRequestOptions extends Omit<RequestInit, 'body' | 'headers'> {
  body?: unknown
  accessToken?: string | null
  headers?: HeadersInit
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${apiBase}${normalizedPath}`
}

function isRawRequestBody(body: unknown): body is BodyInit {
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    return true
  }
  if (typeof Blob !== 'undefined' && body instanceof Blob) {
    return true
  }
  if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) {
    return true
  }
  if (body instanceof ArrayBuffer) {
    return true
  }
  return ArrayBuffer.isView(body)
}

function resolveRequestBody(body: unknown): BodyInit | undefined {
  if (body === undefined) {
    return undefined
  }
  if (isRawRequestBody(body)) {
    return body
  }
  return JSON.stringify(body)
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  if (options.body !== undefined && !isRawRequestBody(options.body) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  if (options.accessToken) {
    headers.set('Authorization', `Bearer ${options.accessToken}`)
  }

  const response = await fetch(buildUrl(path), {
    ...options,
    headers,
    credentials: 'include',
    body: resolveRequestBody(options.body),
  })

  if (!response.ok) {
    throw await toApiClientError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    return undefined as T
  }

  return (await response.json()) as T
}

export function getApiBase(): string {
  return apiBase
}

import type { ErrorResponse } from '@/api/types'

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string | null
  readonly detail: string

  constructor(status: number, detail: string, code: string | null = null) {
    super(detail)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export async function toApiClientError(response: Response): Promise<ApiClientError> {
  let payload: ErrorResponse | null = null

  try {
    payload = (await response.json()) as ErrorResponse
  } catch {
    payload = null
  }

  const detail = payload?.detail ?? (response.statusText || 'Request failed')
  const code = payload?.code ?? null
  return new ApiClientError(response.status, detail, code)
}

export function asUserMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.detail
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unexpected error'
}

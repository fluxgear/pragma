import { apiRequest, type ApiRequestOptions } from '@/api/client'
import { ApiClientError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

export type AuthenticatedApiRequestOptions = Omit<ApiRequestOptions, 'accessToken'>

type AuthenticatedOperation<T> = (accessToken: string) => Promise<T>

async function getAccessToken(forceRefresh = false): Promise<string> {
  const authStore = useAuthStore()
  return await authStore.ensureAccessToken({ forceRefresh })
}

export async function withFreshAccessToken<T>(operation: AuthenticatedOperation<T>): Promise<T> {
  const accessToken = await getAccessToken()

  try {
    return await operation(accessToken)
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 401) {
      const refreshedAccessToken = await getAccessToken(true)
      return await operation(refreshedAccessToken)
    }

    throw error
  }
}

export function authenticatedApiRequest<T>(
  path: string,
  options: AuthenticatedApiRequestOptions = {},
): Promise<T> {
  return withFreshAccessToken((accessToken) =>
    apiRequest<T>(path, {
      ...options,
      accessToken,
    }),
  )
}

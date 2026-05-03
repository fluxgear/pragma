import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { authenticatedApiRequest } from '@/api/authenticated'
import { ApiClientError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const user = {
  id: 'user-1',
  email: 'admin@example.com',
  username: 'admin',
  full_name: 'Admin User',
  is_active: true,
  is_superuser: true,
  roles: ['administrator'],
  permissions: ['users.manage'],
  force_password_change: false,
}

const refreshedSession = {
  access_token: 'fresh-token',
  token_type: 'bearer' as const,
  expires_in: 900,
  user,
}

function seedAuthenticatedStore(accessToken = 'token-123'): void {
  const authStore = useAuthStore()
  authStore.accessToken = accessToken
  authStore.accessTokenExpiresAtMs = Date.now() + 60_000
  authStore.user = user
}

describe('authenticated API requests', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('refreshes a stale access token before issuing the API request', async () => {
    seedAuthenticatedStore('stale-token')
    const authStore = useAuthStore()
    authStore.accessTokenExpiresAtMs = Date.now() - 1

    apiClientMocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/auth/refresh') {
        return Promise.resolve(refreshedSession)
      }
      return Promise.resolve({ ok: true })
    })

    await expect(authenticatedApiRequest('/users')).resolves.toEqual({ ok: true })

    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(1, '/auth/refresh', {
      method: 'POST',
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(2, '/users', {
      accessToken: 'fresh-token',
    })
  })

  it('coalesces concurrent stale-token refreshes into one refresh request', async () => {
    seedAuthenticatedStore('stale-token')
    const authStore = useAuthStore()
    authStore.accessTokenExpiresAtMs = Date.now() - 1

    let resolveRefresh: (value: typeof refreshedSession) => void = () => undefined
    const refreshPromise = new Promise<typeof refreshedSession>((resolve) => {
      resolveRefresh = resolve
    })

    apiClientMocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/auth/refresh') {
        return refreshPromise
      }
      return Promise.resolve({ path })
    })

    const usersPromise = authenticatedApiRequest('/users')
    const rolesPromise = authenticatedApiRequest('/users/roles')
    resolveRefresh(refreshedSession)

    await expect(Promise.all([usersPromise, rolesPromise])).resolves.toEqual([
      { path: '/users' },
      { path: '/users/roles' },
    ])

    const refreshCalls = apiClientMocks.apiRequest.mock.calls.filter(([path]) => path === '/auth/refresh')
    expect(refreshCalls).toHaveLength(1)
    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users', {
      accessToken: 'fresh-token',
    })
    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users/roles', {
      accessToken: 'fresh-token',
    })
  })

  it('refreshes and retries an authenticated API request once after a 401', async () => {
    seedAuthenticatedStore()

    apiClientMocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/auth/refresh') {
        return Promise.resolve(refreshedSession)
      }
      if (path === '/users' && apiClientMocks.apiRequest.mock.calls.length === 1) {
        return Promise.reject(new ApiClientError(401, 'Expired token', 'TOKEN_EXPIRED'))
      }
      return Promise.resolve({ ok: true })
    })

    await expect(authenticatedApiRequest('/users')).resolves.toEqual({ ok: true })

    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(1, '/users', {
      accessToken: 'token-123',
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(2, '/auth/refresh', {
      method: 'POST',
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(3, '/users', {
      accessToken: 'fresh-token',
    })
  })
})

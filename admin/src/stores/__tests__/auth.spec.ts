import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { ApiClientError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

const authApiMocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  getCurrentUser: vi.fn(),
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  refreshSession: vi.fn(),
}))

vi.mock('@/api/auth', () => authApiMocks)

const authPayload = {
  access_token: 'token-123',
  token_type: 'bearer' as const,
  expires_in: 900,
  user: {
    id: 'user-1',
    email: 'admin@example.com',
    username: 'admin',
    full_name: 'Admin User',
    is_active: true,
    is_superuser: true,
    roles: ['administrator'],
    permissions: ['users.manage', 'ai.settings.manage'],
    force_password_change: false,
  },
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('restores a session from the refresh endpoint and stores access token expiry', async () => {
    const now = new Date('2026-04-27T12:00:00Z')
    vi.useFakeTimers()
    vi.setSystemTime(now)
    authApiMocks.refreshSession.mockResolvedValue(authPayload)

    const store = useAuthStore()

    await expect(store.restoreSession()).resolves.toBe(true)
    expect(store.isAuthenticated).toBe(true)
    expect(store.accessToken).toBe('token-123')
    expect(store.expiresIn).toBe(900)
    expect(store.accessTokenExpiresAtMs).toBe(now.getTime() + 900_000)
    expect(store.user?.email).toBe('admin@example.com')
  })

  it('silently clears session state when refresh fails with an auth error', async () => {
    authApiMocks.refreshSession.mockRejectedValue(
      new ApiClientError(401, 'Refresh token is required', 'REFRESH_TOKEN_REQUIRED'),
    )

    const store = useAuthStore()

    await expect(store.restoreSession()).resolves.toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(store.errorMessage).toBeNull()
  })

  it('surfaces non-auth restore failures', async () => {
    authApiMocks.refreshSession.mockRejectedValue(new Error('Backend unavailable'))

    const store = useAuthStore()

    await expect(store.restoreSession()).resolves.toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(store.errorMessage).toBe('Backend unavailable')
  })

  it('coalesces concurrent stale-token refreshes through ensureAccessToken', async () => {
    let resolveRefresh: (value: typeof authPayload) => void = () => undefined
    const refreshPromise = new Promise<typeof authPayload>((resolve) => {
      resolveRefresh = resolve
    })
    authApiMocks.refreshSession.mockReturnValue(refreshPromise)

    const store = useAuthStore()
    store.accessToken = 'stale-token'
    store.accessTokenExpiresAtMs = Date.now() - 1
    store.user = authPayload.user

    const firstTokenPromise = store.ensureAccessToken()
    const secondTokenPromise = store.ensureAccessToken()
    resolveRefresh(authPayload)

    await expect(Promise.all([firstTokenPromise, secondTokenPromise])).resolves.toEqual([
      'token-123',
      'token-123',
    ])
    expect(authApiMocks.refreshSession).toHaveBeenCalledTimes(1)
    expect(store.accessToken).toBe('token-123')
  })

  it('logs in, syncs identity, and logs out', async () => {
    authApiMocks.loginUser.mockResolvedValue(authPayload)
    authApiMocks.getCurrentUser.mockResolvedValue({
      ...authPayload.user,
      full_name: 'Updated Admin',
    })
    authApiMocks.logoutUser.mockResolvedValue(undefined)

    const store = useAuthStore()

    await store.login({
      identity: 'admin@example.com',
      password: 'very-secure-password',
    })

    expect(store.isAuthenticated).toBe(true)
    expect(store.user?.full_name).toBe('Admin User')
    expect(store.hasPermission('users.manage')).toBe(true)

    await store.syncCurrentUser()
    expect(store.user?.full_name).toBe('Updated Admin')

    await store.logout()
    expect(store.isAuthenticated).toBe(false)
    expect(store.accessToken).toBeNull()
  })

  it('rotates the current user password and clears forced-change state', async () => {
    authApiMocks.changePassword.mockResolvedValue({
      ...authPayload.user,
      force_password_change: false,
    })

    const store = useAuthStore()
    store.accessToken = 'token-123'
    store.user = {
      ...authPayload.user,
      force_password_change: true,
    }

    await store.rotateOwnPassword({
      current_password: 'old-password',
      new_password: 'new-password',
    })

    expect(authApiMocks.changePassword).toHaveBeenCalledWith('token-123', {
      current_password: 'old-password',
      new_password: 'new-password',
    })
    expect(store.requiresPasswordChange).toBe(false)
  })
})

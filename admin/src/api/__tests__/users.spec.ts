import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  createUser,
  listRoles,
  listUsers,
  replaceUserRoles,
  resetUserPassword,
  updateUser,
} from '@/api/users'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

describe('users API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('passes the bearer token when listing users', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 })

    await listUsers()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users', {
      accessToken,
    })
  })

  it('passes pagination parameters when listing users', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 50 })

    await listUsers({ limit: 25, offset: 50 })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users?limit=25&offset=50', {
      accessToken,
    })
  })

  it('passes the bearer token when listing roles', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ items: [], total: 0 })

    await listRoles()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users/roles', {
      accessToken,
    })
  })

  it('passes the bearer token when creating a managed user', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'user-1' })

    await createUser({
      email: 'editor@example.com',
      username: 'editor',
      full_name: 'Editor User',
      password: 'very-secure-password',
      is_active: true,
      role_keys: ['editor'],
      force_password_change: true,
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users', {
      accessToken,
      method: 'POST',
      body: {
        email: 'editor@example.com',
        username: 'editor',
        full_name: 'Editor User',
        password: 'very-secure-password',
        is_active: true,
        role_keys: ['editor'],
        force_password_change: true,
      },
    })
  })

  it('passes the bearer token when updating a user', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'user-1' })

    await updateUser('user-1', {
      full_name: 'Updated User',
      is_active: false,
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users/user-1', {
      accessToken,
      method: 'PATCH',
      body: {
        full_name: 'Updated User',
        is_active: false,
      },
    })
  })

  it('passes the bearer token when replacing user roles', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ id: 'user-1' })

    await replaceUserRoles('user-1', {
      role_keys: ['viewer'],
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users/user-1/roles', {
      accessToken,
      method: 'PUT',
      body: {
        role_keys: ['viewer'],
      },
    })
  })

  it('passes the bearer token when resetting a password', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ temporary_password: 'temp-pass' })

    await resetUserPassword('user-1')

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/users/user-1/password-reset', {
      accessToken,
      method: 'POST',
    })
  })
})

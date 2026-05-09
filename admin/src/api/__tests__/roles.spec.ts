import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createRole, listRolesAdmin } from '@/api/roles'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

describe('roles admin API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('passes the bearer token when listing roles through the admin endpoint', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      items: [],
      total: 0,
      permission_definitions: [],
    })

    await listRolesAdmin()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/roles', {
      accessToken,
    })
  })

  it('passes the bearer token and unchanged payload when creating a role', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      role_key: 'regional_editor',
      name: 'Regional Editor',
      description: 'Localized editorial access',
      is_system: false,
      permission_keys: ['content.entries.read'],
    })

    const payload = {
      role_key: 'regional_editor',
      name: 'Regional Editor',
      description: 'Localized editorial access',
      permission_keys: ['content.entries.read', 'media.assets.read'],
    }

    await createRole(payload)

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/roles', {
      accessToken,
      method: 'POST',
      body: payload,
    })
  })
})

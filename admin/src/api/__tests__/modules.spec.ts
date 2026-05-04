import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { listModules, updateModuleState } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

describe('modules API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('passes the bearer token when listing modules', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ items: [], total: 0 })

    await listModules()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/modules', {
      accessToken,
    })
  })

  it('passes the bearer token when updating module state', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ module_id: 'search', enabled: false })

    await updateModuleState('search', { enabled: false })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/modules/search/state', {
      accessToken,
      method: 'PUT',
      body: { enabled: false },
    })
  })
})

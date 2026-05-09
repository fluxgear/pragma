import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { getPrimaryNavigationMenu, replacePrimaryNavigationMenu } from '@/api/navigation'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

describe('navigation API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('passes the bearer token when loading the primary menu', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ key: 'primary', items: [], warnings: [] })

    await getPrimaryNavigationMenu()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/navigation/primary', {
      accessToken,
    })
  })

  it('replaces the primary menu through the backend navigation endpoint', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ key: 'primary', items: [], warnings: [] })

    await replacePrimaryNavigationMenu({
      items: [
        {
          label: 'Home',
          link_type: 'custom_url',
          url: '/',
          enabled: true,
        },
        {
          label: 'About',
          link_type: 'content_entry',
          content_entry_id: 'entry-1',
          enabled: false,
        },
      ],
    })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/navigation/primary', {
      accessToken,
      method: 'PUT',
      body: {
        items: [
          {
            label: 'Home',
            link_type: 'custom_url',
            url: '/',
            enabled: true,
          },
          {
            label: 'About',
            link_type: 'content_entry',
            content_entry_id: 'entry-1',
            enabled: false,
          },
        ],
      },
    })
  })

  it('fails fast when no session access token is available', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    await expect(getPrimaryNavigationMenu()).rejects.toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { listThemes, resetThemeSettings, updateThemeSettings } from '@/api/themes'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

const themeSettingsResponse = {
  active_theme_id: 'default',
  default_theme_id: 'default',
  current_theme_id: 'default',
  persisted_active_theme_id: null,
  design_settings: {
    primary_color: '#2563eb',
    accent_color: '#7c3aed',
    background_color: '#ffffff',
    text_color: '#111827',
    typography_preset: 'system',
    spacing_scale: 'comfortable',
    radius_scale: 'medium',
  },
  design_warnings: [],
  themes: [
    {
      id: 'default',
      name: 'Default',
      version: '1.0.0',
      description: 'Bundled theme',
      author: 'Pragma',
      active: true,
      default: true,
      current: true,
      available: true,
    },
  ],
}

describe('themes API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('fetches discovered themes and settings with the bearer token', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(themeSettingsResponse)

    await listThemes()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/themes', {
      accessToken,
    })
  })

  it('updates active theme and safe design settings through the backend settings route', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(themeSettingsResponse)

    const payload = {
      active_theme_id: 'modern',
      design_settings: {
        primary_color: '#0f766e',
        accent_color: '#7c3aed',
        background_color: '#ffffff',
        text_color: '#111827',
        typography_preset: 'editorial' as const,
        spacing_scale: 'spacious' as const,
        radius_scale: 'large' as const,
      },
    }

    await updateThemeSettings(payload)

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/themes/settings', {
      accessToken,
      method: 'PUT',
      body: payload,
    })
  })

  it('resets persisted settings to backend environment/default behavior', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(themeSettingsResponse)

    await resetThemeSettings()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/themes/settings/reset', {
      accessToken,
      method: 'POST',
    })
  })

  it('fails fast when no session access token is available', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    await expect(listThemes()).rejects.toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

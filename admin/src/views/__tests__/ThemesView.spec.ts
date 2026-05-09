import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { useAuthStore } from '@/stores/auth'
import ThemesView from '@/views/ThemesView.vue'

const themeApiMocks = vi.hoisted(() => ({
  listThemes: vi.fn(),
  resetThemeSettings: vi.fn(),
  updateThemeSettings: vi.fn(),
}))

vi.mock('@/api/themes', () => themeApiMocks)

const accessToken = 'token-123'
const themePermissions = ['themes.manage']

const baseSettingsPayload = {
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
      description: 'Bundled default theme',
      author: 'Pragma',
      active: true,
      default: true,
      current: true,
      available: true,
    },
    {
      id: 'modern',
      name: 'Modern',
      version: '1.2.0',
      description: 'Modern marketing theme',
      author: 'Acme',
      active: false,
      default: false,
      current: false,
      available: true,
    },
  ],
}

const activatedSettingsPayload = {
  ...baseSettingsPayload,
  active_theme_id: 'modern',
  current_theme_id: 'modern',
  persisted_active_theme_id: 'modern',
  themes: baseSettingsPayload.themes.map((theme) => ({
    ...theme,
    active: theme.id === 'modern',
    current: theme.id === 'modern',
  })),
}

const designSavedPayload = {
  ...baseSettingsPayload,
  design_settings: {
    primary_color: '#0f766e',
    accent_color: '#7c3aed',
    background_color: '#ffffff',
    text_color: '#111827',
    typography_preset: 'editorial',
    spacing_scale: 'spacious',
    radius_scale: 'large',
  },
  design_warnings: ['Primary color may not have enough contrast on the background.'],
}

async function mountView(canManage = true) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = accessToken
  authStore.user = {
    id: 'user-1',
    email: 'admin@example.com',
    username: 'admin',
    full_name: 'Admin User',
    is_active: true,
    is_superuser: canManage,
    roles: canManage ? ['administrator'] : ['viewer'],
    assigned_permissions: canManage ? themePermissions : [],
    effective_permissions: canManage ? themePermissions : [],
    has_all_permissions: canManage,
    permission_source: canManage ? 'superuser' : 'roles',
    permissions: canManage ? themePermissions : [],
    force_password_change: false,
  }

  const wrapper = mount(ThemesView, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper }
}

describe('ThemesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    themeApiMocks.listThemes.mockResolvedValue(baseSettingsPayload)
    themeApiMocks.updateThemeSettings.mockResolvedValue(activatedSettingsPayload)
    themeApiMocks.resetThemeSettings.mockResolvedValue(baseSettingsPayload)
  })

  it('loads discovered themes and current/default/persisted settings without claiming live preview', async () => {
    const { wrapper } = await mountView()

    expect(themeApiMocks.listThemes).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Default')
    expect(wrapper.text()).toContain('Modern')
    expect(wrapper.text()).toContain('Active theme')
    expect(wrapper.text()).toContain('default')
    expect(wrapper.text()).toContain('None · environment/default behavior')
    expect(wrapper.text()).toContain('No live theme preview is implemented')
  })

  it('activates the selected discovered theme through the backend settings API', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="theme-card-modern"]').trigger('click')
    await wrapper.get('#themes-activate-btn').trigger('click')
    await flushPromises()

    expect(themeApiMocks.updateThemeSettings).toHaveBeenCalledWith({ active_theme_id: 'modern' })
    expect(wrapper.text()).toContain('Modern activated')
    expect(wrapper.text()).toContain('modern')
  })

  it('resets persisted settings to backend environment/default behavior', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('#themes-reset-btn').trigger('click')
    await flushPromises()

    expect(themeApiMocks.resetThemeSettings).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Theme settings reset to environment/default behavior.')
  })

  it('saves safe design settings and displays backend design warnings', async () => {
    themeApiMocks.updateThemeSettings.mockResolvedValue(designSavedPayload)

    const { wrapper } = await mountView()

    await wrapper.get('#theme-primary-color').setValue('#0f766e')
    await wrapper.get('#theme-typography-preset').setValue('editorial')
    await wrapper.get('#theme-spacing-scale').setValue('spacious')
    await wrapper.get('#theme-radius-scale').setValue('large')
    await wrapper.get('#themes-save-design-btn').trigger('click')
    await flushPromises()

    expect(themeApiMocks.updateThemeSettings).toHaveBeenCalledWith({
      design_settings: {
        primary_color: '#0f766e',
        accent_color: '#7c3aed',
        background_color: '#ffffff',
        text_color: '#111827',
        typography_preset: 'editorial',
        spacing_scale: 'spacious',
        radius_scale: 'large',
      },
    })
    expect(wrapper.text()).toContain('Design settings saved.')
    expect(wrapper.text()).toContain('Primary color may not have enough contrast')
  })

  it('renders an empty state when the backend discovers no themes', async () => {
    themeApiMocks.listThemes.mockResolvedValue({
      ...baseSettingsPayload,
      themes: [],
    })

    const { wrapper } = await mountView()

    expect(wrapper.get('[data-testid="themes-empty-state"]').text()).toContain('No themes have been discovered')
  })

  it('renders load and activation error states', async () => {
    themeApiMocks.listThemes.mockResolvedValue(baseSettingsPayload)
    themeApiMocks.updateThemeSettings.mockRejectedValue(new Error('Theme activation failed'))

    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="theme-card-modern"]').trigger('click')
    await wrapper.get('#themes-activate-btn').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Theme activation failed')

    themeApiMocks.listThemes.mockRejectedValue(new Error('Theme API unavailable'))
    const second = await mountView()

    expect(second.wrapper.text()).toContain('Theme API unavailable')
  })

  it('does not load mutable theme state for users missing themes.manage', async () => {
    const { wrapper } = await mountView(false)

    expect(themeApiMocks.listThemes).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Theme administration requires themes.manage')
    expect(wrapper.get('#themes-refresh-btn').attributes('disabled')).toBeDefined()
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import AppShellLayout from '@/layouts/AppShellLayout.vue'
import { useAuthStore } from '@/stores/auth'

const realtimeApiMocks = vi.hoisted(() => ({
  buildRealtimeWebSocketProtocols: vi.fn(() => ['pragma-realtime', 'ticket']),
  buildRealtimeWebSocketUrl: vi.fn(() => 'ws://localhost/api/v1/realtime/ws'),
  createRealtimeTicket: vi.fn(),
}))

vi.mock('@/api/realtime', () => realtimeApiMocks)

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/app', name: 'dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/app/content', name: 'content', component: { template: '<div>Content</div>' } },
      { path: '/app/content-models', name: 'content-models', component: { template: '<div>Content models</div>' } },
      { path: '/app/media', name: 'media', component: { template: '<div>Media</div>' } },
      { path: '/app/ai', name: 'ai-settings', component: { template: '<div>AI settings</div>' } },
      { path: '/app/themes', name: 'themes', component: { template: '<div>Themes</div>' } },
      { path: '/app/navigation', name: 'navigation', component: { template: '<div>Navigation</div>' } },
      { path: '/app/modules', name: 'modules', component: { template: '<div>Modules</div>' } },
      { path: '/app/users', name: 'users', component: { template: '<div>Users</div>' } },
      { path: '/app/roles', name: 'roles', component: { template: '<div>Roles</div>' } },
      { path: '/app/account', name: 'account', component: { template: '<div>Account</div>' } },
      { path: '/login', name: 'login', component: { template: '<div>Login</div>' } },
    ],
  })
}

async function mountLayout() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = 'token-123'
  authStore.user = {
    id: 'root-1',
    email: 'admin@example.com',
    username: 'admin',
    full_name: 'Admin User',
    is_active: true,
    is_superuser: false,
    roles: ['administrator'],
    assigned_permissions: [
      'ai.settings.manage',
      'content.entries.read',
      'content.types.read',
      'media.assets.read',
      'modules.manage',
      'navigation.manage',
      'roles.manage',
      'themes.manage',
      'users.manage',
    ],
    effective_permissions: [
      'ai.settings.manage',
      'content.entries.read',
      'content.types.read',
      'media.assets.read',
      'modules.manage',
      'navigation.manage',
      'roles.manage',
      'themes.manage',
      'users.manage',
    ],
    has_all_permissions: false,
    permission_source: 'roles' as const,
    permissions: [
      'ai.settings.manage',
      'content.entries.read',
      'content.types.read',
      'media.assets.read',
      'modules.manage',
      'navigation.manage',
      'roles.manage',
      'themes.manage',
      'users.manage',
    ],
    force_password_change: false,
  }

  const router = createTestRouter()
  await router.push('/app')
  await router.isReady()

  const wrapper = mount(AppShellLayout, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()

  return { router, wrapper }
}

function findNavButton(wrapper: ReturnType<typeof mount>, label: string) {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().includes(label))
  if (button === undefined) {
    throw new Error(`${label} navigation button not found`)
  }
  return button
}

function mockCompactNavigation(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn((query: string) => ({
      matches: query === '(max-width: 960px)' ? matches : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(() => true),
    })),
  })
}

describe('AppShellLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCompactNavigation(false)
    realtimeApiMocks.createRealtimeTicket.mockRejectedValue(new Error('Realtime unavailable in test'))
  })

  it('renders the commercial navigation hierarchy with accessible skip navigation', async () => {
    const { wrapper } = await mountLayout()

    expect(wrapper.get('.skip-link').attributes('href')).toBe('#admin-main')
    expect(wrapper.get('#admin-main').attributes('tabindex')).toBe('-1')
    expect(wrapper.text()).toContain('Commercial CMS workbench')
    expect((wrapper.get('details.shell__nav-drawer').element as HTMLDetailsElement).open).toBe(true)

    for (const section of [
      'Content',
      'Structure',
      'Design',
      'Assets',
      'People',
      'Extensions',
      'Settings',
      'Observability',
    ]) {
      expect(wrapper.text()).toContain(section)
    }

    expect(findNavButton(wrapper, 'Dashboard').attributes('aria-current')).toBe('page')
    expect(findNavButton(wrapper, 'Roles').attributes('disabled')).toBeUndefined()

    const navigationButton = findNavButton(wrapper, 'Navigation menus')
    expect(navigationButton.attributes('disabled')).toBeUndefined()
    expect(navigationButton.text()).not.toContain('Later')

    const themeDesignButton = findNavButton(wrapper, 'Theme design')
    expect(themeDesignButton.attributes('disabled')).toBeUndefined()
    expect(themeDesignButton.text()).not.toContain('Later')
  })

  it('starts compact navigation collapsed and closes it after mobile navigation', async () => {
    mockCompactNavigation(true)
    const { router, wrapper } = await mountLayout()

    const drawer = wrapper.get('details.shell__nav-drawer')
    const drawerElement = drawer.element as HTMLDetailsElement

    expect(drawerElement.open).toBe(false)
    expect(drawer.get('summary').text()).toContain('Navigation')

    drawerElement.open = true
    await drawer.trigger('toggle')

    expect(drawerElement.open).toBe(true)

    const mediaButton = findNavButton(wrapper, 'Media library')
    await mediaButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('media')
    expect((wrapper.get('details.shell__nav-drawer').element as HTMLDetailsElement).open).toBe(false)
  })

  it('routes implemented workbench navigation without broken coming-later links', async () => {
    const { router, wrapper } = await mountLayout()

    const modulesButton = findNavButton(wrapper, 'Modules')
    expect(modulesButton.attributes('disabled')).toBeUndefined()

    await modulesButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('modules')

    const navigationButton = findNavButton(wrapper, 'Navigation menus')
    expect(navigationButton.attributes('disabled')).toBeUndefined()

    await navigationButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('navigation')

    const themesButton = findNavButton(wrapper, 'Theme design')
    expect(themesButton.attributes('disabled')).toBeUndefined()

    await themesButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('themes')

    const rolesButton = findNavButton(wrapper, 'Roles')
    expect(rolesButton.attributes('disabled')).toBeUndefined()

    await rolesButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('roles')

    const mediaButton = findNavButton(wrapper, 'Media library')
    await mediaButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('media')

    const contentModelsButton = findNavButton(wrapper, 'Content models')
    expect(contentModelsButton.attributes('disabled')).toBeUndefined()

    await contentModelsButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('content-models')
  })

  it('keeps permissioned existing surfaces visible but locked when permissions are missing', async () => {
    const { wrapper } = await mountLayout()
    const authStore = useAuthStore()

    authStore.user = {
      ...authStore.user!,
      permissions: ['modules.manage'],
    }
    await flushPromises()

    const navigationButton = findNavButton(wrapper, 'Navigation menus')
    expect(navigationButton.attributes('disabled')).toBeDefined()
    expect(navigationButton.attributes('title')).toBe('Requires navigation.manage.')
    expect(navigationButton.text()).toContain('Locked')

    const usersButton = findNavButton(wrapper, 'Users')
    expect(usersButton.attributes('disabled')).toBeDefined()
    expect(usersButton.attributes('title')).toBe('Requires users.manage.')
    expect(usersButton.text()).toContain('Locked')

    const contentModelsButton = findNavButton(wrapper, 'Content models')
    expect(contentModelsButton.attributes('disabled')).toBeDefined()
    expect(contentModelsButton.attributes('title')).toBe('Requires content.types.read.')
    expect(contentModelsButton.text()).toContain('Locked')

    const rolesButton = findNavButton(wrapper, 'Roles')
    expect(rolesButton.attributes('disabled')).toBeDefined()
    expect(rolesButton.attributes('title')).toBe('Requires roles.manage.')
    expect(rolesButton.text()).toContain('Locked')

    expect(findNavButton(wrapper, 'Modules').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).not.toContain('Theme design')
  })
})

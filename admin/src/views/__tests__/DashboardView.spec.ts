import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiClientError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import DashboardView from '@/views/DashboardView.vue'

const authApiMocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  getCurrentUser: vi.fn(),
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  refreshSession: vi.fn(),
}))

const systemApiMocks = vi.hoisted(() => ({
  fetchReadinessStatus: vi.fn(),
}))

vi.mock('@/api/auth', () => authApiMocks)
vi.mock('@/api/system', () => systemApiMocks)

const readinessStatus = {
  status: 'ok',
  database: 'up',
  schema_ready: true,
  capabilities: {
    pg_trgm: {
      available: true,
      installed: true,
      default_version: '1.0',
      installed_version: '1.0',
    },
  },
}

const authPayload = {
  id: 'user-1',
  email: 'admin@example.com',
  username: 'admin',
  full_name: 'Admin User',
  is_active: true,
  is_superuser: true,
  roles: ['administrator'],
  permissions: ['users.manage', 'ai.settings.manage', 'modules.manage'],
  force_password_change: false,
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = 'token-123'
  authStore.user = authPayload
  authStore.initialized = true
  authStore.startupError = null

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/app', name: 'dashboard', component: DashboardView },
      { path: '/login', name: 'login', component: { template: '<div>login</div>' } },
    ],
  })

  await router.push('/app')
  await router.isReady()

  const wrapper = mount(DashboardView, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()

  return { router, wrapper }
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    systemApiMocks.fetchReadinessStatus.mockResolvedValue(readinessStatus)
    authApiMocks.loginUser.mockResolvedValue(undefined)
    authApiMocks.logoutUser.mockResolvedValue(undefined)
    authApiMocks.refreshSession.mockResolvedValue(undefined)
  })

  it('redirects back to login when identity sync fails after mount', async () => {
    authApiMocks.getCurrentUser.mockRejectedValue(
      new ApiClientError(401, 'Authentication required', 'AUTH_REQUIRED'),
    )

    const { router } = await mountView()

    await flushPromises()

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/app')
  })
})

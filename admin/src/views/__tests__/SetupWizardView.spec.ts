import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiClientError } from '@/api/errors'
import DashboardView from '@/views/DashboardView.vue'
import LoginView from '@/views/LoginView.vue'
import SetupWizardView from '@/views/SetupWizardView.vue'

const installApiMocks = vi.hoisted(() => ({
  bootstrapInstall: vi.fn(),
  fetchInstallStatus: vi.fn(),
}))

const systemApiMocks = vi.hoisted(() => ({
  fetchReadinessStatus: vi.fn(),
}))

const authApiMocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  getCurrentUser: vi.fn(),
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  refreshSession: vi.fn(),
}))

vi.mock('@/api/install', () => installApiMocks)
vi.mock('@/api/system', () => systemApiMocks)
vi.mock('@/api/auth', () => authApiMocks)

const capabilityStatus = {
  available: true,
  installed: true,
  default_version: '1.0',
  installed_version: '1.0',
}

const installStatus = {
  schema_ready: true,
  is_installed: false,
  superuser_exists: false,
  capabilities: {
    pg_trgm: capabilityStatus,
    pgvector: capabilityStatus,
  },
}

const readinessStatus = {
  status: 'ok',
  database: 'up',
  schema_ready: true,
  capabilities: installStatus.capabilities,
}

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

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/setup', name: 'setup', component: SetupWizardView },
      { path: '/app', name: 'dashboard', component: DashboardView },
      { path: '/login', name: 'login', component: LoginView },
    ],
  })
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createTestRouter()
  await router.push('/setup')
  await router.isReady()

  const wrapper = mount(SetupWizardView, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()

  return { router, wrapper }
}

describe('SetupWizardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    installApiMocks.fetchInstallStatus.mockResolvedValue(installStatus)
    systemApiMocks.fetchReadinessStatus.mockResolvedValue(readinessStatus)
    installApiMocks.bootstrapInstall.mockResolvedValue({
      installed: true,
      user: authPayload.user,
    })
    authApiMocks.loginUser.mockResolvedValue(authPayload)
    authApiMocks.getCurrentUser.mockResolvedValue(authPayload.user)
    authApiMocks.logoutUser.mockResolvedValue(undefined)
    authApiMocks.refreshSession.mockRejectedValue(
      new ApiClientError(401, 'Refresh token is required', 'REFRESH_TOKEN_REQUIRED'),
    )
  })

  it('bootstraps the first super-admin and routes into the dashboard shell', async () => {
    const { router, wrapper } = await mountView()

    await wrapper.get('#setup-email').setValue('admin@example.com')
    await wrapper.get('#setup-username').setValue('admin')
    await wrapper.get('#setup-full-name').setValue('Admin User')
    await wrapper.get('input#setup-password').setValue('very-secure-password')
    await wrapper.get('input#setup-confirm-password').setValue('very-secure-password')

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(installApiMocks.bootstrapInstall).toHaveBeenCalledWith({
      email: 'admin@example.com',
      username: 'admin',
      password: 'very-secure-password',
      full_name: 'Admin User',
    })
    expect(authApiMocks.loginUser).toHaveBeenCalledWith({
      identity: 'admin@example.com',
      password: 'very-secure-password',
    })
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('surfaces bootstrap conflicts without leaving setup', async () => {
    installApiMocks.bootstrapInstall.mockRejectedValue(
      new ApiClientError(409, 'Install bootstrap has already completed', 'INSTALL_ALREADY_COMPLETED'),
    )

    const { router, wrapper } = await mountView()

    await wrapper.get('#setup-email').setValue('admin@example.com')
    await wrapper.get('#setup-username').setValue('admin')
    await wrapper.get('input#setup-password').setValue('very-secure-password')
    await wrapper.get('input#setup-confirm-password').setValue('very-secure-password')

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('setup')
    expect(wrapper.text()).toContain('Install bootstrap has already completed')
  })
})

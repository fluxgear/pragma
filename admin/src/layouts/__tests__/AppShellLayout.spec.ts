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
      { path: '/app/modules', name: 'modules', component: { template: '<div>Modules</div>' } },
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
    permissions: ['modules.manage'],
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

describe('AppShellLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    realtimeApiMocks.createRealtimeTicket.mockRejectedValue(new Error('Realtime unavailable in test'))
  })

  it('includes module administration in the workbench navigation', async () => {
    const { router, wrapper } = await mountLayout()

    const modulesButton = wrapper.findAll('button').find((button) => button.text().includes('Modules'))
    if (modulesButton === undefined) {
      throw new Error('Modules navigation button not found')
    }

    expect(modulesButton.attributes('disabled')).toBeUndefined()

    await modulesButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('modules')
  })
})

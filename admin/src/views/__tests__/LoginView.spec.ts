import { describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import LoginView from '@/views/LoginView.vue'

const authApiMocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  getCurrentUser: vi.fn(),
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  refreshSession: vi.fn(),
}))

vi.mock('@/api/auth', () => authApiMocks)

async function mountView(initialPath = '/login') {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: LoginView },
      { path: '/app', name: 'dashboard', component: { template: '<div>dashboard</div>' } },
      { path: '/setup', name: 'setup', component: { template: '<div>setup</div>' } },
    ],
  })

  await router.push(initialPath)
  await router.isReady()

  const wrapper = mount(LoginView, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()

  return { router, wrapper }
}

describe('LoginView', () => {
  it('does not offer a guard-bounced setup shortcut', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).not.toContain('Review setup status')
  })

  it('shows password-change feedback handed off through the login URL', async () => {
    const { wrapper } = await mountView('/login?passwordChanged=1')

    expect(wrapper.text()).toContain('Password changed successfully. Please sign in again.')
  })
})

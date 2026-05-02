import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { useAuthStore } from '@/stores/auth'
import AccountView from '@/views/AccountView.vue'

const authApiMocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  getCurrentUser: vi.fn(),
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  refreshSession: vi.fn(),
}))
const routerReplace = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: routerReplace }),
}))

vi.mock('@/api/auth', () => authApiMocks)

async function mountView(forcePasswordChange = false) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = 'token-123'
  authStore.user = {
    id: 'user-1',
    email: 'admin@example.com',
    username: 'admin',
    full_name: 'Admin User',
    is_active: true,
    is_superuser: true,
    roles: ['administrator'],
    permissions: ['users.manage'],
    force_password_change: forcePasswordChange,
  }

  const wrapper = mount(AccountView, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()

  return { authStore, wrapper }
}

describe('AccountView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routerReplace.mockResolvedValue(undefined)
    authApiMocks.changePassword.mockResolvedValue({
      id: 'user-1',
      email: 'admin@example.com',
      username: 'admin',
      full_name: 'Admin User',
      is_active: true,
      is_superuser: true,
      roles: ['administrator'],
      permissions: ['users.manage'],
      force_password_change: false,
    })
  })

  it('submits a password change through the auth store and requires reauthentication', async () => {
    const { authStore, wrapper } = await mountView(true)

    await wrapper.get('input#current-password').setValue('old-password')
    await wrapper.get('input#new-password').setValue('new-password')
    await wrapper.get('input#confirm-password').setValue('new-password')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(authApiMocks.changePassword).toHaveBeenCalledWith('token-123', {
      current_password: 'old-password',
      new_password: 'new-password',
    })
    expect(authStore.accessToken).toBeNull()
    expect(authStore.user).toBeNull()
    expect(routerReplace).toHaveBeenCalledWith({ name: 'login', query: { passwordChanged: '1' } })
  })

  it('blocks submission when confirmation does not match', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('input#new-password').setValue('new-password')
    await wrapper.get('input#confirm-password').setValue('different-password')
    await wrapper.get('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('The new password confirmation does not match.')
    expect(authApiMocks.changePassword).not.toHaveBeenCalled()
  })
})

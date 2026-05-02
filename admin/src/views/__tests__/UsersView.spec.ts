import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { useAuthStore } from '@/stores/auth'
import UsersView from '@/views/UsersView.vue'

const userApiMocks = vi.hoisted(() => ({
  createUser: vi.fn(),
  listRoles: vi.fn(),
  listUsers: vi.fn(),
  replaceUserRoles: vi.fn(),
  resetUserPassword: vi.fn(),
  updateUser: vi.fn(),
}))

vi.mock('@/api/users', () => userApiMocks)

const usersPayload = {
  items: [
    {
      id: 'user-1',
      email: 'editor@example.com',
      username: 'editor',
      full_name: 'Editor User',
      is_active: true,
      is_superuser: false,
      roles: ['editor'],
      permissions: ['content.entries.read'],
      force_password_change: false,
      last_login_at: null,
      password_changed_at: null,
      created_at: '2026-04-27T00:00:00Z',
      updated_at: '2026-04-27T00:00:00Z',
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
}

const rolesPayload = {
  items: [
    {
      role_key: 'editor',
      name: 'Editor',
      description: 'Manage content and media',
      is_system: true,
      permission_keys: ['content.entries.read'],
    },
    {
      role_key: 'viewer',
      name: 'Viewer',
      description: 'Read-only access',
      is_system: true,
      permission_keys: ['content.entries.read'],
    },
  ],
  total: 2,
}

async function mountView() {
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
    is_superuser: true,
    roles: ['administrator'],
    permissions: ['users.manage'],
    force_password_change: false,
  }

  const wrapper = mount(UsersView, {
    attachTo: document.body,
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper }
}

describe('UsersView', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    userApiMocks.listUsers.mockResolvedValue(usersPayload)
    userApiMocks.listRoles.mockResolvedValue(rolesPayload)
    userApiMocks.createUser.mockResolvedValue(usersPayload.items[0])
    userApiMocks.replaceUserRoles.mockResolvedValue({
      ...usersPayload.items[0],
      roles: ['viewer'],
    })
    userApiMocks.resetUserPassword.mockResolvedValue({ temporary_password: 'temp-pass-123' })
    userApiMocks.updateUser.mockResolvedValue({
      ...usersPayload.items[0],
      is_active: false,
    })
  })
  it('loads users and roles on mount', async () => {
    const { wrapper } = await mountView()

    expect(userApiMocks.listUsers).toHaveBeenCalledTimes(1)
    expect(userApiMocks.listUsers).toHaveBeenCalledWith({ limit: 50, offset: 0 })
    expect(userApiMocks.listRoles).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Editor User')
    expect(wrapper.text()).toContain('editor@example.com')
  })

  it('creates a new user from the dialog', async () => {
    const { wrapper } = await mountView()

    const newUserButton = wrapper.findAll('button').find((button) => button.text().includes('New user'))
    if (!newUserButton) {
      throw new Error('New user button not found')
    }

    await newUserButton.trigger('click')
    await flushPromises()

    const createEmail = document.body.querySelector('#create-email')
    const createUsername = document.body.querySelector('#create-username')
    const createFullName = document.body.querySelector('#create-full-name')
    const createPassword = document.body.querySelector('input#create-password')
    const createPasswordLabel = document.body.querySelector('label[for="create-password"]')
    const createForm = document.body.querySelector('form')

    if (!(createEmail instanceof HTMLInputElement)) {
      throw new Error('Create email input not found')
    }
    if (!(createUsername instanceof HTMLInputElement)) {
      throw new Error('Create username input not found')
    }
    if (!(createFullName instanceof HTMLInputElement)) {
      throw new Error('Create full name input not found')
    }
    if (!(createPassword instanceof HTMLInputElement)) {
      throw new Error('Create password input not found')
    }
    if (!(createPasswordLabel instanceof HTMLLabelElement)) {
      throw new Error('Create password label not found')
    }
    if (!(createForm instanceof HTMLFormElement)) {
      throw new Error('Create user form not found')
    }

    expect(createPasswordLabel.htmlFor).toBe('create-password')

    createEmail.value = 'viewer@example.com'
    createEmail.dispatchEvent(new Event('input'))
    createUsername.value = 'viewer'
    createUsername.dispatchEvent(new Event('input'))
    createFullName.value = 'Viewer User'
    createFullName.dispatchEvent(new Event('input'))
    createPassword.value = 'very-secure-password'
    createPassword.dispatchEvent(new Event('input'))
    createForm.dispatchEvent(new Event('submit'))
    await flushPromises()
    await flushPromises()

    expect(userApiMocks.createUser).toHaveBeenCalled()
  })

  it('requires confirmation before resetting a password and shows the temporary credential', async () => {
    const { wrapper } = await mountView()

    const resetButton = wrapper.findAll('button').find((button) => button.text().includes('Reset password'))
    if (!resetButton) {
      throw new Error('Reset password button not found')
    }

    await resetButton.trigger('click')
    await flushPromises()

    expect(userApiMocks.resetUserPassword).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Reset the password for Editor User?')

    const confirmButton = document.body.querySelector('[data-testid="user-confirm-action"]')
    if (!(confirmButton instanceof HTMLButtonElement)) {
      throw new Error('User action confirmation button not found')
    }

    confirmButton.click()
    await flushPromises()
    await flushPromises()

    expect(userApiMocks.resetUserPassword).toHaveBeenCalledWith('user-1')
    expect(wrapper.text()).toContain('Temporary password: temp-pass-123')
  })

  it('requires confirmation before deactivating a user', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="user-toggle-active"]').trigger('click')
    await flushPromises()

    expect(userApiMocks.updateUser).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Deactivate Editor User?')

    const confirmButton = document.body.querySelector('[data-testid="user-confirm-action"]')
    if (!(confirmButton instanceof HTMLButtonElement)) {
      throw new Error('User action confirmation button not found')
    }

    confirmButton.click()
    await flushPromises()
    await flushPromises()

    expect(userApiMocks.updateUser).toHaveBeenCalledWith('user-1', { is_active: false })
  })

  it('requires confirmation before reactivating a user', async () => {
    userApiMocks.listUsers.mockResolvedValueOnce({
      ...usersPayload,
      items: [{ ...usersPayload.items[0], is_active: false }],
    })
    userApiMocks.updateUser.mockResolvedValueOnce({
      ...usersPayload.items[0],
      is_active: true,
    })
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="user-toggle-active"]').trigger('click')
    await flushPromises()

    expect(userApiMocks.updateUser).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Activate Editor User?')

    const confirmButton = document.body.querySelector('[data-testid="user-confirm-action"]')
    if (!(confirmButton instanceof HTMLButtonElement)) {
      throw new Error('User action confirmation button not found')
    }

    confirmButton.click()
    await flushPromises()
    await flushPromises()

    expect(userApiMocks.updateUser).toHaveBeenCalledWith('user-1', { is_active: true })
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { ApiClientError } from '@/api/errors'
import RolesView from '@/views/RolesView.vue'

const rolesApiMocks = vi.hoisted(() => ({
  createRole: vi.fn(),
  listRolesAdmin: vi.fn(),
}))

vi.mock('@/api/roles', () => rolesApiMocks)


class ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

vi.stubGlobal('ResizeObserver', ResizeObserver)
const permissionDefinitions = [
  {
    key: 'content.entries.read',
    name: 'Read content entries',
    description: 'View content entry records',
    domain: 'content',
  },
  {
    key: 'content.entries.publish',
    name: 'Publish content entries',
    description: 'Publish content entry records',
    domain: 'content',
  },
  {
    key: 'roles.manage',
    name: 'Manage roles',
    description: 'Create and administer roles',
    domain: 'identity',
  },
]

const rolesPayload = {
  items: [
    {
      role_key: 'administrator',
      name: 'Administrator',
      description: 'Full administrative access',
      is_system: true,
      permission_keys: ['roles.manage', 'content.entries.read'],
    },
    {
      role_key: 'regional_editor',
      name: 'Regional Editor',
      description: 'Localized editorial access',
      is_system: false,
      permission_keys: ['content.entries.read'],
    },
  ],
  total: 2,
  permission_definitions: permissionDefinitions,
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(RolesView, {
    attachTo: document.body,
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper }
}

function findButton(wrapper: ReturnType<typeof mount>, label: string) {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().includes(label))
  if (button === undefined) {
    throw new Error(`${label} button not found`)
  }
  return button
}

function setDialogInput(selector: string, value: string): void {
  const input = document.body.querySelector(selector)
  if (!(input instanceof HTMLInputElement) && !(input instanceof HTMLTextAreaElement)) {
    throw new Error(`${selector} input not found`)
  }

  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

function setPermissionChecked(permissionKey: string): void {
  const checkbox = document.body.querySelector(`[data-testid=\"permission-checkbox-${permissionKey}\"]`)
  if (!(checkbox instanceof HTMLInputElement)) {
    throw new Error(`${permissionKey} checkbox not found`)
  }

  checkbox.checked = true
  checkbox.dispatchEvent(new Event('change', { bubbles: true }))
}

function submitDialogForm(): void {
  const form = document.body.querySelector('form')
  if (!(form instanceof HTMLFormElement)) {
    throw new Error('Create role form not found')
  }

  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
}

describe('RolesView', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    rolesApiMocks.listRolesAdmin.mockResolvedValue(rolesPayload)
    rolesApiMocks.createRole.mockResolvedValue({
      role_key: 'publisher',
      name: 'Publisher',
      description: 'Can publish content',
      is_system: false,
      permission_keys: ['content.entries.publish'],
    })
  })

  it('renders loading while the initial roles request is pending', async () => {
    let resolveRoles: (payload: typeof rolesPayload) => void = () => undefined
    rolesApiMocks.listRolesAdmin.mockReturnValue(new Promise((resolve) => {
      resolveRoles = resolve
    }))

    const wrapper = mount(RolesView, {
      global: {
        plugins: [createPinia(), [PrimeVue, { theme: { preset: Aura } }]],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Loading roles and permissions')

    resolveRoles(rolesPayload)
    await flushPromises()

    expect(wrapper.text()).toContain('Administrator')
  })

  it('loads roles and permission groups on mount', async () => {
    const { wrapper } = await mountView()

    expect(rolesApiMocks.listRolesAdmin).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Administrator')
    expect(wrapper.text()).toContain('System')
    expect(wrapper.text()).toContain('regional_editor')
    expect(wrapper.text()).toContain('Custom')
    expect(wrapper.text()).toContain('Full administrative access')
    expect(wrapper.text()).toContain('Read content entries (content.entries.read)')
    expect(wrapper.text()).toContain('content')
    expect(wrapper.text()).toContain('identity')
    expect(wrapper.text()).toContain('Manage roles')
  })

  it('makes system roles explicitly read-only without edit or delete affordances', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Built-in roles are read-only product roles')
    expect(wrapper.text()).toContain('Read-only system role. No edit or delete controls are available.')
    expect(wrapper.findAll('button').some((button) => /^(Edit|Delete)$/.test(button.text()))).toBe(false)
  })

  it('renders a GET failure state', async () => {
    rolesApiMocks.listRolesAdmin.mockRejectedValue(new Error('Roles service unavailable'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Roles service unavailable')
    expect(wrapper.text()).toContain('Roles could not be loaded.')
  })

  it('renders an empty state when the backend returns no roles', async () => {
    rolesApiMocks.listRolesAdmin.mockResolvedValue({
      items: [],
      total: 0,
      permission_definitions: permissionDefinitions,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('No roles returned by the backend.')
    expect(wrapper.text()).toContain('Built-in system roles should always be present.')
  })

  it('creates a custom role, refreshes the list, and closes the dialog', async () => {
    const refreshedPayload = {
      ...rolesPayload,
      items: [
        ...rolesPayload.items,
        {
          role_key: 'publisher',
          name: 'Publisher',
          description: 'Can publish content',
          is_system: false,
          permission_keys: ['content.entries.publish'],
        },
      ],
      total: 3,
    }
    rolesApiMocks.listRolesAdmin
      .mockResolvedValueOnce(rolesPayload)
      .mockResolvedValueOnce(refreshedPayload)

    const { wrapper } = await mountView()

    await findButton(wrapper, 'New custom role').trigger('click')
    await flushPromises()

    setDialogInput('#create-role-key', 'publisher')
    setDialogInput('#create-role-name', 'Publisher')
    setDialogInput('#create-role-description', 'Can publish content')
    setPermissionChecked('content.entries.publish')
    submitDialogForm()
    await flushPromises()
    await flushPromises()

    expect(rolesApiMocks.createRole).toHaveBeenCalledWith({
      role_key: 'publisher',
      name: 'Publisher',
      description: 'Can publish content',
      permission_keys: ['content.entries.publish'],
    })
    expect(rolesApiMocks.listRolesAdmin).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Publisher')
    expect(document.body.querySelector('#create-role-key')).toBeNull()
  })

  it('surfaces backend create conflicts in the dialog', async () => {
    rolesApiMocks.createRole.mockRejectedValue(
      new ApiClientError(409, 'Role key already exists.', 'ROLE_KEY_CONFLICT'),
    )

    const { wrapper } = await mountView()

    await findButton(wrapper, 'New custom role').trigger('click')
    await flushPromises()

    setDialogInput('#create-role-key', 'administrator')
    setDialogInput('#create-role-name', 'Administrator clone')
    setPermissionChecked('roles.manage')
    submitDialogForm()
    await flushPromises()

    expect(rolesApiMocks.createRole).toHaveBeenCalledWith({
      role_key: 'administrator',
      name: 'Administrator clone',
      description: null,
      permission_keys: ['roles.manage'],
    })
    expect(document.body.textContent).toContain('A role with this key already exists. Role key already exists.')
    expect(document.body.querySelector('#create-role-key')).not.toBeNull()
  })
})

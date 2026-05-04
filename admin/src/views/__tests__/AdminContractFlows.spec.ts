import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import type {
  AdminUserListResponse,
  AdminUserResponse,
  InstallStatusResponse,
  RoleListResponse,
  RoleResponse,
  TokenResponse,
} from '@/api/types'
import { resolveNavigation } from '@/router/guards'
import { useAuthStore } from '@/stores/auth'
import { useInstallStore } from '@/stores/install'
import UsersView from '@/views/UsersView.vue'

interface CapturedRequest {
  path: string
  init: RequestInit | undefined
  body: unknown
}

const installedStatus = {
  schema_ready: true,
  is_installed: true,
  superuser_exists: true,
  capabilities: {},
} satisfies InstallStatusResponse

const editorUser = {
  id: 'user-1',
  email: 'editor@example.com',
  username: 'editor',
  full_name: 'Editor User',
  is_active: true,
  is_superuser: false,
  roles: ['editor'],
  permissions: ['content.entries.read', 'content.entries.write'],
  force_password_change: false,
  last_login_at: null,
  password_changed_at: null,
  created_at: '2026-04-27T00:00:00Z',
  updated_at: '2026-04-27T00:00:00Z',
} satisfies AdminUserResponse

const editorRole = {
  role_key: 'editor',
  name: 'Editor',
  description: 'Manage content and media',
  is_system: true,
  permission_keys: ['content.entries.read', 'content.entries.write', 'media.assets.read'],
} satisfies RoleResponse

const viewerRole = {
  role_key: 'viewer',
  name: 'Viewer',
  description: 'Read-only access',
  is_system: true,
  permission_keys: ['content.entries.read'],
} satisfies RoleResponse

const usersList = {
  items: [editorUser],
  total: 1,
  limit: 50,
  offset: 0,
} satisfies AdminUserListResponse

const roleList = {
  items: [editorRole, viewerRole],
  total: 2,
} satisfies RoleListResponse

function tokenPayload(permissions: string[], isSuperuser = false): TokenResponse {
  return {
    access_token: 'token-123',
    token_type: 'bearer',
    expires_in: 900,
    user: {
      id: 'current-user-1',
      email: 'current@example.com',
      username: 'current',
      full_name: 'Current User',
      is_active: true,
      is_superuser: isSuperuser,
      roles: isSuperuser ? ['administrator'] : ['editor'],
      permissions,
      force_password_change: false,
    },
  }
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function requestPath(input: RequestInfo | URL): string {
  const rawUrl = typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url
  const url = new URL(rawUrl, 'http://localhost')
  return `${url.pathname}${url.search}`
}

function requestBody(init: RequestInit | undefined): unknown {
  if (typeof init?.body !== 'string') {
    return undefined
  }
  return JSON.parse(init.body)
}

function headerValue(init: RequestInit | undefined, name: string): string | null {
  return new Headers(init?.headers).get(name)
}

function stubFetch(
  responder: (path: string, init: RequestInit | undefined, body: unknown) => Response | Promise<Response>,
): CapturedRequest[] {
  const requests: CapturedRequest[] = []

  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = requestPath(input)
    const body = requestBody(init)
    requests.push({ path, init, body })
    return responder(path, init, body)
  }))

  return requests
}

function makeGuardRoute(name: string, requiresPermission: string) {
  return {
    name,
    fullPath: `/app/${name}`,
    meta: { requiresAuth: true, requiresPermission },
  }
}

async function mountUsersView(accessToken = 'token-123') {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = accessToken
  authStore.user = tokenPayload(['users.manage']).user

  const wrapper = mount(UsersView, {
    attachTo: document.body,
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return wrapper
}

describe('admin backend contract flows', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    vi.unstubAllGlobals()
  })

  it('routes a restored backend session away from users admin without users.manage', async () => {
    const requests = stubFetch((path) => {
      if (path === '/api/v1/install/status') {
        return jsonResponse(installedStatus)
      }
      if (path === '/api/v1/auth/refresh') {
        return jsonResponse(tokenPayload(['content.entries.read']))
      }
      throw new Error(`Unexpected admin contract request: ${path}`)
    })
    const pinia = createPinia()
    setActivePinia(pinia)

    const result = await resolveNavigation(
      makeGuardRoute('users', 'users.manage'),
      useInstallStore(),
      useAuthStore(),
    )

    expect(result).toEqual({ name: 'dashboard' })
    expect(useAuthStore().hasPermission('content.entries.read')).toBe(true)
    expect(useAuthStore().hasPermission('users.manage')).toBe(false)
    expect(requests.map((request) => request.path)).toEqual([
      '/api/v1/install/status',
      '/api/v1/auth/refresh',
    ])
  })

  it('hydrates users admin and reset-password workflow through backend-shaped HTTP contracts', async () => {
    const requests = stubFetch((path, init) => {
      if (path === '/api/v1/users?limit=50&offset=0') {
        expect(headerValue(init, 'Authorization')).toBe('Bearer token-123')
        return jsonResponse(usersList)
      }
      if (path === '/api/v1/users/roles') {
        expect(headerValue(init, 'Authorization')).toBe('Bearer token-123')
        return jsonResponse(roleList)
      }
      if (path === '/api/v1/users/user-1/password-reset') {
        return jsonResponse({ temporary_password: 'temp-pass-123' })
      }
      throw new Error(`Unexpected admin contract request: ${path}`)
    })

    const wrapper = await mountUsersView()

    expect(wrapper.text()).toContain('Editor User')
    expect(wrapper.text()).toContain('editor@example.com')
    expect(wrapper.text()).toContain('Showing 1-1 of 1 users')

    await wrapper.get('[data-testid="user-reset-password"]').trigger('click')
    await flushPromises()

    expect(requests.some((request) => request.path === '/api/v1/users/user-1/password-reset')).toBe(false)
    expect(document.body.textContent).toContain('Reset the password for Editor User?')

    const confirmButton = document.body.querySelector('[data-testid="user-confirm-action"]')
    if (!(confirmButton instanceof HTMLButtonElement)) {
      throw new Error('User action confirmation button not found')
    }

    confirmButton.click()
    await flushPromises()
    await flushPromises()

    const resetRequest = requests.find((request) => request.path === '/api/v1/users/user-1/password-reset')
    expect(resetRequest?.init?.method).toBe('POST')
    expect(headerValue(resetRequest?.init, 'Authorization')).toBe('Bearer token-123')
    expect(document.body.textContent).toContain('Temporary password ready')
    expect(document.body.textContent).not.toContain('temp-pass-123')

    const revealButton = document.body.querySelector('[data-testid="temporary-password-reveal"]')
    if (!(revealButton instanceof HTMLButtonElement)) {
      throw new Error('Temporary password reveal button not found')
    }
    revealButton.click()
    await flushPromises()

    expect(document.body.textContent).toContain('temp-pass-123')
    expect(requests.filter((request) => request.path === '/api/v1/users?limit=50&offset=0')).toHaveLength(2)
  })
})

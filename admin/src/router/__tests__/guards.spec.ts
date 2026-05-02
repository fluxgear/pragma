import { describe, expect, it, vi } from 'vitest'

import { evaluateNavigation, resolveNavigation } from '@/router/guards'

function makeRoute(
  name: string,
  meta: {
    guestOnly?: boolean
    requiresAuth?: boolean
    requiresSuperuser?: boolean
    requiresPermission?: string
    allowForcedPasswordChange?: boolean
  } = {},
  fullPath = `/${name}`,
) {
  return {
    name,
    meta,
    fullPath,
  }
}

describe('evaluateNavigation', () => {
  it('routes uninstalled systems to setup', () => {
    expect(
      evaluateNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), {
        isInstalled: false,
        isAuthenticated: false,
        isSuperuser: false,
        permissions: [],
        forcePasswordChange: false,
      }),
    ).toEqual({ name: 'setup' })
  })

  it('allows the setup wizard on uninstalled systems', () => {
    expect(
      evaluateNavigation(makeRoute('setup', {}, '/setup'), {
        isInstalled: false,
        isAuthenticated: false,
        isSuperuser: false,
        permissions: [],
        forcePasswordChange: false,
      }),
    ).toBe(true)
  })


  it('allows the top-level not-found route on uninstalled systems', () => {
    expect(
      evaluateNavigation(makeRoute('not-found', {}, '/missing'), {
        isInstalled: false,
        isAuthenticated: false,
        isSuperuser: false,
        permissions: [],
        forcePasswordChange: false,
      }),
    ).toBe(true)
  })
  it('routes anonymous users to login for protected routes', () => {
    expect(
      evaluateNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), {
        isInstalled: true,
        isAuthenticated: false,
        isSuperuser: false,
        permissions: [],
        forcePasswordChange: false,
      }),
    ).toEqual({
      name: 'login',
      query: { redirect: '/app' },
    })
  })

  it('routes authenticated users away from guest-only routes', () => {
    expect(
      evaluateNavigation(makeRoute('login', { guestOnly: true }, '/login'), {
        isInstalled: true,
        isAuthenticated: true,
        isSuperuser: false,
        permissions: [],
        forcePasswordChange: false,
      }),
    ).toEqual({ name: 'dashboard' })
  })

  it('uses the home route to select login or dashboard', () => {
    expect(
      evaluateNavigation(makeRoute('home', {}, '/'), {
        isInstalled: true,
        isAuthenticated: false,
        isSuperuser: false,
        permissions: [],
        forcePasswordChange: false,
      }),
    ).toEqual({ name: 'login' })

    expect(
      evaluateNavigation(makeRoute('home', {}, '/'), {
        isInstalled: true,
        isAuthenticated: true,
        isSuperuser: true,
        permissions: [],
        forcePasswordChange: false,
      }),
    ).toEqual({ name: 'dashboard' })
  })

  it('routes users away from routes requiring missing permissions', () => {
    expect(
      evaluateNavigation(
        makeRoute('ai-settings', { requiresAuth: true, requiresPermission: 'ai.settings.manage' }, '/app/ai'),
        {
          isInstalled: true,
          isAuthenticated: true,
          isSuperuser: false,
          permissions: ['content.entries.read'],
          forcePasswordChange: false,
        },
      ),
    ).toEqual({ name: 'dashboard' })
  })

  it('routes forced-password-change users to the account route', () => {
    expect(
      evaluateNavigation(makeRoute('content', { requiresAuth: true, requiresPermission: 'content.entries.read' }, '/app/content'), {
        isInstalled: true,
        isAuthenticated: true,
        isSuperuser: false,
        permissions: ['content.entries.read'],
        forcePasswordChange: true,
      }),
    ).toEqual({ name: 'account' })
  })

  it('allows the account route during forced password rotation', () => {
    expect(
      evaluateNavigation(makeRoute('account', { requiresAuth: true, allowForcedPasswordChange: true }, '/app/account'), {
        isInstalled: true,
        isAuthenticated: true,
        isSuperuser: false,
        permissions: [],
        forcePasswordChange: true,
      }),
    ).toBe(true)
  })
})

describe('resolveNavigation', () => {
  it('routes non-home navigation back to the boot screen when install status checks fail', async () => {
    const installStore = {
      isInstalled: true,
      ensureStatus: vi.fn().mockRejectedValue(new Error('Backend unavailable')),
    }
    const authStore = {
      initialized: false,
      isAuthenticated: false,
      user: null,
      errorMessage: null,
      startupError: null,
      hasPermission: vi.fn().mockReturnValue(false),
      ensureInitialized: vi.fn(),
    }

    await expect(
      resolveNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), installStore, authStore),
    ).resolves.toEqual({ name: 'home' })
    expect(authStore.ensureInitialized).not.toHaveBeenCalled()
  })

  it('routes non-home navigation back to the boot screen when session restoration records a startup error', async () => {
    const installStore = {
      isInstalled: true,
      ensureStatus: vi.fn().mockResolvedValue(undefined),
    }
    const authStore = {
      initialized: false,
      isAuthenticated: false,
      user: null,
      errorMessage: null as string | null,
      startupError: null as string | null,
      hasPermission: vi.fn().mockReturnValue(false),
      ensureInitialized: vi.fn().mockImplementation(async () => {
        authStore.errorMessage = 'Backend unavailable'
        authStore.startupError = 'Backend unavailable'
      }),
    }

    await expect(
      resolveNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), installStore, authStore),
    ).resolves.toEqual({ name: 'home' })
    expect(authStore.ensureInitialized).toHaveBeenCalledWith(true)
  })

  it('keeps routing through the boot screen while a startup error persists after initialization', async () => {
    const installStore = {
      isInstalled: true,
      ensureStatus: vi.fn().mockResolvedValue(undefined),
    }
    const authStore = {
      initialized: true,
      isAuthenticated: false,
      user: null,
      errorMessage: 'Backend unavailable',
      startupError: 'Backend unavailable',
      hasPermission: vi.fn().mockReturnValue(false),
      ensureInitialized: vi.fn(),
    }

    await expect(
      resolveNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), installStore, authStore),
    ).resolves.toEqual({ name: 'home' })
  })

  it('does not treat non-startup auth errors as boot failures', async () => {
    const installStore = {
      isInstalled: true,
      ensureStatus: vi.fn().mockResolvedValue(undefined),
    }
    const authStore = {
      initialized: true,
      isAuthenticated: false,
      user: null,
      errorMessage: 'Invalid credentials',
      startupError: null,
      hasPermission: vi.fn().mockReturnValue(false),
      ensureInitialized: vi.fn(),
    }

    await expect(
      resolveNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), installStore, authStore),
    ).resolves.toEqual({
      name: 'login',
      query: { redirect: '/app' },
    })
  })

  it('allows the boot route to render when startup checks fail', async () => {
    const installStore = {
      isInstalled: false,
      ensureStatus: vi.fn().mockRejectedValue(new Error('Backend unavailable')),
    }
    const authStore = {
      initialized: false,
      isAuthenticated: false,
      user: null,
      errorMessage: null,
      startupError: null,
      hasPermission: vi.fn().mockReturnValue(false),
      ensureInitialized: vi.fn(),
    }

    await expect(resolveNavigation(makeRoute('home', {}, '/'), installStore, authStore)).resolves.toBe(true)
  })
})

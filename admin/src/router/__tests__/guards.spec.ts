import { describe, expect, it, vi } from 'vitest'

import { evaluateNavigation, resolveNavigation } from '@/router/guards'

function makeRoute(
  name: string,
  meta: { guestOnly?: boolean; requiresAuth?: boolean; requiresSuperuser?: boolean } = {},
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
      }),
    ).toEqual({ name: 'setup' })
  })

  it('allows the setup wizard on uninstalled systems', () => {
    expect(
      evaluateNavigation(makeRoute('setup', {}, '/setup'), {
        isInstalled: false,
        isAuthenticated: false,
        isSuperuser: false,
      }),
    ).toBe(true)
  })

  it('routes anonymous users to login for protected routes', () => {
    expect(
      evaluateNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), {
        isInstalled: true,
        isAuthenticated: false,
        isSuperuser: false,
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
      }),
    ).toEqual({ name: 'dashboard' })
  })

  it('uses the home route to select login or dashboard', () => {
    expect(
      evaluateNavigation(makeRoute('home', {}, '/'), {
        isInstalled: true,
        isAuthenticated: false,
        isSuperuser: false,
      }),
    ).toEqual({ name: 'login' })

    expect(
      evaluateNavigation(makeRoute('home', {}, '/'), {
        isInstalled: true,
        isAuthenticated: true,
        isSuperuser: true,
      }),
    ).toEqual({ name: 'dashboard' })
  })

  it('routes non-superusers away from superuser-only routes', () => {
    expect(
      evaluateNavigation(
        makeRoute('ai-settings', { requiresAuth: true, requiresSuperuser: true }, '/app/ai'),
        {
          isInstalled: true,
          isAuthenticated: true,
          isSuperuser: false,
        },
      ),
    ).toEqual({ name: 'dashboard' })
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
      ensureInitialized: vi.fn(),
    }

    await expect(resolveNavigation(makeRoute('home', {}, '/'), installStore, authStore)).resolves.toBe(true)
  })
})

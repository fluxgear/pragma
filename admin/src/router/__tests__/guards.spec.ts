import { describe, expect, it } from 'vitest'

import { evaluateNavigation } from '@/router/guards'

function makeRoute(
  name: string,
  meta: { guestOnly?: boolean; requiresAuth?: boolean } = {},
  fullPath = `/${name}` ,
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
      }),
    ).toEqual({ name: 'setup' })
  })

  it('allows the setup wizard on uninstalled systems', () => {
    expect(
      evaluateNavigation(makeRoute('setup', {}, '/setup'), {
        isInstalled: false,
        isAuthenticated: false,
      }),
    ).toBe(true)
  })

  it('routes anonymous users to login for protected routes', () => {
    expect(
      evaluateNavigation(makeRoute('dashboard', { requiresAuth: true }, '/app'), {
        isInstalled: true,
        isAuthenticated: false,
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
      }),
    ).toEqual({ name: 'dashboard' })
  })

  it('uses the home route to select login or dashboard', () => {
    expect(
      evaluateNavigation(makeRoute('home', {}, '/'), {
        isInstalled: true,
        isAuthenticated: false,
      }),
    ).toEqual({ name: 'login' })

    expect(
      evaluateNavigation(makeRoute('home', {}, '/'), {
        isInstalled: true,
        isAuthenticated: true,
      }),
    ).toEqual({ name: 'dashboard' })
  })
})

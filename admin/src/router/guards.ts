import type { RouteLocationRaw, RouteMeta } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    guestOnly?: boolean
    requiresAuth?: boolean
    title?: string
  }
}

export interface GuardRoute {
  name: string | symbol | null | undefined
  fullPath: string
  meta: RouteMeta
}

export interface GuardState {
  isInstalled: boolean
  isAuthenticated: boolean
}

export function evaluateNavigation(
  route: GuardRoute,
  state: GuardState,
): true | RouteLocationRaw {
  const routeName = typeof route.name === 'string' ? route.name : null

  if (!state.isInstalled) {
    return routeName === 'setup' ? true : { name: 'setup' }
  }

  if (routeName === 'home') {
    return state.isAuthenticated ? { name: 'dashboard' } : { name: 'login' }
  }

  if (routeName === 'setup') {
    return state.isAuthenticated ? { name: 'dashboard' } : { name: 'login' }
  }

  if (route.meta.requiresAuth && !state.isAuthenticated) {
    return {
      name: 'login',
      query: {
        redirect: route.fullPath,
      },
    }
  }

  if (route.meta.guestOnly && state.isAuthenticated) {
    return { name: 'dashboard' }
  }

  return true
}

import type { RouteLocationRaw, RouteMeta } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    guestOnly?: boolean
    requiresAuth?: boolean
    requiresSuperuser?: boolean
    requiresPermission?: string
    allowForcedPasswordChange?: boolean
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
  isSuperuser: boolean
  permissions: string[]
  forcePasswordChange: boolean
}

export interface NavigationInstallStore {
  isInstalled: boolean
  ensureStatus(): Promise<unknown>
}

export interface NavigationAuthStore {
  initialized: boolean
  isAuthenticated: boolean
  user: { is_superuser: boolean; permissions: string[]; force_password_change: boolean } | null
  errorMessage: string | null
  startupError: string | null
  hasPermission(permission: string): boolean
  ensureInitialized(shouldRestore: boolean): Promise<void>
}

function fallbackToBoot(route: GuardRoute): true | RouteLocationRaw {
  return typeof route.name === 'string' && route.name === 'home' ? true : { name: 'home' }
}

export function evaluateNavigation(
  route: GuardRoute,
  state: GuardState,
): true | RouteLocationRaw {
  const routeName = typeof route.name === 'string' ? route.name : null

  if (!state.isInstalled) {
    return routeName === 'setup' || routeName === 'not-found' ? true : { name: 'setup' }
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

  if (state.forcePasswordChange && !route.meta.allowForcedPasswordChange) {
    return { name: 'account' }
  }

  if (route.meta.requiresPermission && !state.permissions.includes(route.meta.requiresPermission) && !state.isSuperuser) {
    return { name: 'dashboard' }
  }

  if (route.meta.requiresSuperuser && !state.isSuperuser) {
    return { name: 'dashboard' }
  }

  return true
}

export async function resolveNavigation(
  route: GuardRoute,
  installStore: NavigationInstallStore,
  authStore: NavigationAuthStore,
): Promise<true | RouteLocationRaw> {
  try {
    await installStore.ensureStatus()
    await authStore.ensureInitialized(installStore.isInstalled)
  } catch {
    return fallbackToBoot(route)
  }

  if (installStore.isInstalled && authStore.startupError) {
    return fallbackToBoot(route)
  }

  return evaluateNavigation(route, {
    isInstalled: installStore.isInstalled,
    isAuthenticated: authStore.isAuthenticated,
    isSuperuser: authStore.user?.is_superuser === true,
    permissions: authStore.user?.permissions ?? [],
    forcePasswordChange: authStore.user?.force_password_change === true,
  })
}

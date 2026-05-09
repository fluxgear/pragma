import { describe, expect, it } from 'vitest'

import { router } from '@/router'

describe('admin router routes', () => {
  it('preserves the boot route at the root path', () => {
    expect(router.resolve('/').name).toBe('home')
  })

  it('renders the top-level not-found route for unknown admin URLs', () => {
    const resolved = router.resolve('/missing-admin-route')

    expect(resolved.name).toBe('not-found')
    expect(resolved.redirectedFrom).toBeUndefined()
  })


  it('routes content models through the authenticated app shell without weakening entries permissions', () => {
    const entries = router.resolve('/app/content')
    const models = router.resolve('/app/content-models')

    expect(entries.name).toBe('content')
    expect(entries.meta.requiresPermission).toBe('content.entries.read')
    expect(models.name).toBe('content-models')
    expect(models.meta.requiresPermission).toBe('content.types.read')
  })

  it('routes module administration through the authenticated app shell', () => {
    const resolved = router.resolve('/app/modules')

    expect(resolved.name).toBe('modules')
    expect(resolved.meta.requiresPermission).toBe('modules.manage')
  })

  it('routes role administration through the authenticated app shell', () => {
    const resolved = router.resolve('/app/roles')

    expect(resolved.name).toBe('roles')
    expect(resolved.meta.requiresPermission).toBe('roles.manage')
  })

  it('routes theme administration through the authenticated app shell', () => {
    const resolved = router.resolve('/app/themes')

    expect(resolved.name).toBe('themes')
    expect(resolved.meta.requiresPermission).toBe('themes.manage')
  })

  it('routes navigation administration through navigation.manage', () => {
    const resolved = router.resolve('/app/navigation')

    expect(resolved.name).toBe('navigation')
    expect(resolved.meta.requiresPermission).toBe('navigation.manage')
  })
  it('keeps in-shell unknown app URLs on the authenticated app not-found route', () => {
    expect(router.resolve('/app/missing-section').name).toBe('app-not-found')
  })
})

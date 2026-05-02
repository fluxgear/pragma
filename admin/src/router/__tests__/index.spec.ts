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

  it('keeps in-shell unknown app URLs on the authenticated app not-found route', () => {
    expect(router.resolve('/app/missing-section').name).toBe('app-not-found')
  })
})

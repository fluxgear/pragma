import { beforeEach, describe, expect, it, vi } from 'vitest'

import { bootstrapInstall } from '@/api/install'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

describe('install API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends the operator setup secret as a bootstrap header', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({ installed: true })

    const payload = {
      email: 'admin@example.com',
      username: 'admin',
      password: 'very-secure-password',
      full_name: null,
    }

    await bootstrapInstall(payload, '  operator-setup-secret-1234567890  ')

    const requestOptions = apiClientMocks.apiRequest.mock.calls[0]?.[1]
    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/install/bootstrap', {
      method: 'POST',
      headers: expect.any(Headers),
      body: payload,
    })
    expect(new Headers(requestOptions.headers).get('X-Pragma-Setup-Secret')).toBe(
      'operator-setup-secret-1234567890',
    )
  })
})

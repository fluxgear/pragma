import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  buildRealtimeWebSocketProtocols,
  buildRealtimeWebSocketUrl,
  createRealtimeTicket,
} from '@/api/realtime'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  getApiBase: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

describe('realtime API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'access-token-123'
    authStore.user = {
      id: 'user-1',
      email: 'admin@example.com',
      username: 'admin',
      full_name: 'Admin',
      is_active: true,
      is_superuser: true,
      roles: ['administrator'],
      permissions: ['content.entries.read'],
      force_password_change: false,
    }
  })

  it('issues realtime tickets through the authenticated API helper', async () => {
    apiClientMocks.apiRequest.mockResolvedValue({
      ticket: 'ticket-123',
      expires_at: '2026-04-27T19:00:00Z',
    })

    await createRealtimeTicket()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/realtime/ticket', {
      method: 'POST',
      accessToken: 'access-token-123',
    })
  })

  it('derives token-free websocket URLs from same-origin api base', () => {
    apiClientMocks.getApiBase.mockReturnValue('/api/v1')

    const url = new URL(buildRealtimeWebSocketUrl())

    expect(url.protocol).toBe('ws:')
    expect(url.pathname).toBe('/api/v1/realtime/stream')
    expect(url.search).toBe('')
  })

  it('derives token-free websocket URLs from explicit HTTPS api base', () => {
    apiClientMocks.getApiBase.mockReturnValue('https://admin.example.com/api/v1')

    const url = buildRealtimeWebSocketUrl()

    expect(url).toBe('wss://admin.example.com/api/v1/realtime/stream')
  })

  it('builds realtime ticket websocket subprotocols', () => {
    expect(buildRealtimeWebSocketProtocols('ticket-xyz')).toEqual([
      'pragma.realtime.ticket.ticket-xyz',
    ])
  })

  it('fails fast when session access token is unavailable', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    await expect(createRealtimeTicket()).rejects.toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

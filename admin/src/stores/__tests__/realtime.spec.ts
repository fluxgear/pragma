import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { RealtimeEventEnvelope } from '@/api/types'
import {
  __setRealtimeWebSocketFactoryForTests,
  useRealtimeStore,
} from '@/stores/realtime'
import { useAuthStore } from '@/stores/auth'

const realtimeApiMocks = vi.hoisted(() => ({
  buildRealtimeWebSocketUrl: vi.fn(),
  createRealtimeTicket: vi.fn(),
}))

vi.mock('@/api/realtime', () => realtimeApiMocks)

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  url: string
  readyState = FakeWebSocket.CONNECTING

  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent<unknown>) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null

  close = vi.fn((code?: number, reason?: string) => {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.({ code: code ?? 1000, reason: reason ?? '', wasClean: true } as CloseEvent)
  })

  constructor(url: string) {
    this.url = url
  }

  emitOpen(): void {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  emitMessage(payload: unknown): void {
    this.onmessage?.({ data: payload } as MessageEvent<unknown>)
  }

  emitClose(code: number): void {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.({ code, reason: '', wasClean: true } as CloseEvent)
  }
}

describe('useRealtimeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.spyOn(Math, 'random').mockReturnValue(0)

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

    realtimeApiMocks.createRealtimeTicket.mockResolvedValue({
      ticket: 'ticket-1',
      expires_at: '2026-04-27T19:00:00Z',
    })
    realtimeApiMocks.buildRealtimeWebSocketUrl.mockImplementation(
      (ticket: string) => `ws://localhost/api/v1/realtime/stream?ticket=${ticket}`,
    )
  })

  afterEach(() => {
    __setRealtimeWebSocketFactoryForTests(null)
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('connects only for authenticated sessions', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null
    authStore.user = null

    const store = useRealtimeStore()
    store.start()

    await vi.runAllTimersAsync()
    expect(realtimeApiMocks.createRealtimeTicket).not.toHaveBeenCalled()
    expect(store.connectionState).toBe('offline')
  })

  it('resets reconnect attempts and emits resync when socket opens', async () => {
    const sockets: FakeWebSocket[] = []
    __setRealtimeWebSocketFactoryForTests((url: string) => {
      const socket = new FakeWebSocket(url)
      sockets.push(socket)
      return socket as unknown as WebSocket
    })

    const store = useRealtimeStore()
    const resyncSpy = vi.fn()
    store.subscribeResync(resyncSpy)

    store.start()
    await Promise.resolve()

    expect(realtimeApiMocks.createRealtimeTicket).toHaveBeenCalledTimes(1)
    sockets[0].emitOpen()

    expect(store.connectionState).toBe('live')
    expect(store.reconnectAttempts).toBe(0)
    expect(resyncSpy).toHaveBeenCalledTimes(1)
  })

  it('coalesces repeated starts while ticket request is pending', async () => {
    const sockets: FakeWebSocket[] = []
    let resolveTicket: ((value: { ticket: string; expires_at: string }) => void) | null = null
    realtimeApiMocks.createRealtimeTicket.mockImplementation(
      () => new Promise((resolve) => {
        resolveTicket = resolve
      }),
    )
    __setRealtimeWebSocketFactoryForTests((url: string) => {
      const socket = new FakeWebSocket(url)
      sockets.push(socket)
      return socket as unknown as WebSocket
    })

    const store = useRealtimeStore()
    store.start()
    store.start()
    await Promise.resolve()

    expect(realtimeApiMocks.createRealtimeTicket).toHaveBeenCalledTimes(1)
    expect(sockets).toHaveLength(0)
    expect(resolveTicket).not.toBeNull()

    resolveTicket?.({
      ticket: 'ticket-1',
      expires_at: '2026-04-27T19:00:00Z',
    })
    await Promise.resolve()

    expect(sockets).toHaveLength(1)
  })

  it('reconnects with capped exponential backoff after transient close', async () => {
    const sockets: FakeWebSocket[] = []
    __setRealtimeWebSocketFactoryForTests((url: string) => {
      const socket = new FakeWebSocket(url)
      sockets.push(socket)
      return socket as unknown as WebSocket
    })

    const store = useRealtimeStore()
    store.start()
    await Promise.resolve()

    sockets[0].emitOpen()
    sockets[0].emitClose(1011)

    expect(store.connectionState).toBe('reconnecting')
    expect(store.reconnectAttempts).toBe(1)

    await vi.advanceTimersByTimeAsync(400)
    await Promise.resolve()

    expect(realtimeApiMocks.createRealtimeTicket).toHaveBeenCalledTimes(2)
    expect(sockets).toHaveLength(2)
  })

  it('stops reconnect attempts when websocket closes with policy violation', async () => {
    const sockets: FakeWebSocket[] = []
    __setRealtimeWebSocketFactoryForTests((url: string) => {
      const socket = new FakeWebSocket(url)
      sockets.push(socket)
      return socket as unknown as WebSocket
    })

    const store = useRealtimeStore()
    store.start()
    await Promise.resolve()

    sockets[0].emitOpen()
    sockets[0].emitClose(1008)

    await vi.runAllTimersAsync()
    expect(store.connectionState).toBe('offline')
    expect(realtimeApiMocks.createRealtimeTicket).toHaveBeenCalledTimes(1)
  })

  it('stop() closes the socket and clears reconnect timers', async () => {
    const sockets: FakeWebSocket[] = []
    __setRealtimeWebSocketFactoryForTests((url: string) => {
      const socket = new FakeWebSocket(url)
      sockets.push(socket)
      return socket as unknown as WebSocket
    })

    const store = useRealtimeStore()
    store.start()
    await Promise.resolve()

    sockets[0].emitOpen()
    store.stop()
    await vi.runAllTimersAsync()

    expect(store.connectionState).toBe('offline')
    expect(sockets[0].close).toHaveBeenCalled()
    expect(realtimeApiMocks.createRealtimeTicket).toHaveBeenCalledTimes(1)
  })

  it('ignores malformed or unknown envelopes and dispatches valid events', async () => {
    const sockets: FakeWebSocket[] = []
    __setRealtimeWebSocketFactoryForTests((url: string) => {
      const socket = new FakeWebSocket(url)
      sockets.push(socket)
      return socket as unknown as WebSocket
    })

    const store = useRealtimeStore()
    const handler = vi.fn()
    store.subscribe(handler)

    store.start()
    await Promise.resolve()

    sockets[0].emitOpen()
    sockets[0].emitMessage('not-json')
    sockets[0].emitMessage(
      JSON.stringify({
        version: 1,
        id: 'evt-1',
        type: 'unknown.type',
        resource: 'x',
        action: 'x',
        occurred_at: '2026-04-27T19:00:00Z',
        data: {},
      }),
    )

    const validEnvelope: RealtimeEventEnvelope = {
      version: 1,
      id: 'evt-2',
      type: 'content.entry.updated',
      resource: 'content.entry',
      action: 'updated',
      resource_id: 'entry-1',
      occurred_at: '2026-04-27T19:00:00Z',
      actor_id: 'user-1',
      data: { content_type_id: 'type-1' },
    }
    sockets[0].emitMessage(JSON.stringify(validEnvelope))

    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler).toHaveBeenCalledWith(validEnvelope)
  })
})

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { buildRealtimeWebSocketUrl, createRealtimeTicket } from '@/api/realtime'
import type { RealtimeEventEnvelope, RealtimeEventType } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

type RealtimeConnectionState = 'offline' | 'connecting' | 'reconnecting' | 'live'
type RealtimeEventHandler = (event: RealtimeEventEnvelope) => void
type RealtimeResyncHandler = () => void

const MIN_RECONNECT_MS = 500
const MAX_RECONNECT_MS = 30_000

let websocketFactory: (url: string) => WebSocket = (url: string) => new WebSocket(url)

export function __setRealtimeWebSocketFactoryForTests(
  factory: ((url: string) => WebSocket) | null,
): void {
  websocketFactory = factory ?? ((url: string) => new WebSocket(url))
}

function shouldConnectSession(authStore: ReturnType<typeof useAuthStore>): boolean {
  return authStore.isAuthenticated && !authStore.requiresPasswordChange && authStore.accessToken !== null
}

function isRealtimeEventType(value: unknown): value is RealtimeEventType {
  return (
    value === 'content.entry.created'
    || value === 'content.entry.updated'
    || value === 'content.entry.deleted'
    || value === 'realtime.resync_required'
  )
}

function parseRealtimeEnvelope(payload: unknown): RealtimeEventEnvelope | null {
  if (typeof payload !== 'string') {
    return null
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(payload)
  } catch {
    return null
  }

  if (typeof parsed !== 'object' || parsed === null) {
    return null
  }

  const candidate = parsed as Record<string, unknown>
  if (
    candidate.version !== 1
    || typeof candidate.id !== 'string'
    || !isRealtimeEventType(candidate.type)
    || typeof candidate.resource !== 'string'
    || typeof candidate.action !== 'string'
    || typeof candidate.occurred_at !== 'string'
    || typeof candidate.data !== 'object'
    || candidate.data === null
  ) {
    return null
  }

  return {
    version: 1,
    id: candidate.id,
    type: candidate.type,
    resource: candidate.resource,
    action: candidate.action,
    resource_id: typeof candidate.resource_id === 'string' ? candidate.resource_id : undefined,
    occurred_at: candidate.occurred_at,
    actor_id: typeof candidate.actor_id === 'string' ? candidate.actor_id : undefined,
    data: candidate.data as Record<string, unknown>,
  }
}

function computeReconnectDelayMs(attempt: number): number {
  const exponent = Math.max(0, attempt - 1)
  const baseDelay = Math.min(MAX_RECONNECT_MS, MIN_RECONNECT_MS * 2 ** exponent)
  const jitterMultiplier = 0.8 + Math.random() * 0.4
  return Math.round(Math.min(MAX_RECONNECT_MS, baseDelay * jitterMultiplier))
}

export const useRealtimeStore = defineStore('realtime', () => {
  const authStore = useAuthStore()

  const connectionState = ref<RealtimeConnectionState>('offline')
  const reconnectAttempts = ref(0)

  const isLive = computed(() => connectionState.value === 'live')

  const eventHandlers = new Set<RealtimeEventHandler>()
  const resyncHandlers = new Set<RealtimeResyncHandler>()

  let socket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let connectionAttemptInFlight = false
  let connectionAttemptSerial = 0
  let started = false

  function emitEvent(envelope: RealtimeEventEnvelope): void {
    eventHandlers.forEach((handler) => handler(envelope))
  }

  function emitResync(): void {
    resyncHandlers.forEach((handler) => handler())
  }

  function clearReconnectTimer(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function closeSocket(code = 1000, reason = 'client stop'): void {
    const activeSocket = socket
    socket = null
    if (activeSocket === null) {
      return
    }

    if (activeSocket.readyState === WebSocket.OPEN || activeSocket.readyState === WebSocket.CONNECTING) {
      activeSocket.close(code, reason)
    }
  }

  function scheduleReconnect(): void {
    if (!started || reconnectTimer !== null) {
      return
    }

    if (!shouldConnectSession(authStore)) {
      connectionState.value = 'offline'
      return
    }

    reconnectAttempts.value += 1
    connectionState.value = 'reconnecting'

    const delayMs = computeReconnectDelayMs(reconnectAttempts.value)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      void connect()
    }, delayMs)
  }
  async function connect(): Promise<void> {
    if (!started || socket !== null || connectionAttemptInFlight || !shouldConnectSession(authStore)) {
      if (!shouldConnectSession(authStore)) {
        connectionAttemptInFlight = false
        connectionState.value = 'offline'
      }
      return
    }

    connectionAttemptSerial += 1
    const attemptSerial = connectionAttemptSerial
    connectionAttemptInFlight = true
    connectionState.value = reconnectAttempts.value > 0 ? 'reconnecting' : 'connecting'

    let ticket: string
    try {
      const ticketResponse = await createRealtimeTicket()
      ticket = ticketResponse.ticket
    } catch {
      connectionAttemptInFlight = false
      scheduleReconnect()
      return
    }

    if (attemptSerial !== connectionAttemptSerial) {
      return
    }

    if (!started || !shouldConnectSession(authStore)) {
      connectionAttemptInFlight = false
      connectionState.value = 'offline'
      return
    }

    const websocket = websocketFactory(buildRealtimeWebSocketUrl(ticket))
    socket = websocket
    connectionAttemptInFlight = false

    websocket.onopen = () => {
      if (socket !== websocket) {
        return
      }
      reconnectAttempts.value = 0
      connectionState.value = 'live'
      emitResync()
    }

    websocket.onmessage = (messageEvent: MessageEvent<unknown>) => {
      const envelope = parseRealtimeEnvelope(messageEvent.data)
      if (envelope === null) {
        return
      }
      emitEvent(envelope)
      if (envelope.type === 'realtime.resync_required') {
        emitResync()
      }
    }

    websocket.onerror = () => {
      // Rely on close handling for reconnect behavior.
    }

    websocket.onclose = (closeEvent: CloseEvent) => {
      if (socket === websocket) {
        socket = null
      }

      if (!started) {
        connectionState.value = 'offline'
        return
      }

      if (closeEvent.code === 1008) {
        started = false
        clearReconnectTimer()
        connectionState.value = 'offline'
        void authStore.syncCurrentUser()
        return
      }

      scheduleReconnect()
    }
  }
  function start(): void {
    started = true
    clearReconnectTimer()
    void connect()
  }
  function stop(): void {
    started = false
    connectionAttemptInFlight = false
    reconnectAttempts.value = 0
    connectionAttemptSerial += 1
    clearReconnectTimer()
    closeSocket()
    connectionState.value = 'offline'
  }

  function subscribe(handler: RealtimeEventHandler): () => void {
    eventHandlers.add(handler)
    return () => {
      eventHandlers.delete(handler)
    }
  }

  function subscribeResync(handler: RealtimeResyncHandler): () => void {
    resyncHandlers.add(handler)
    return () => {
      resyncHandlers.delete(handler)
    }
  }

  return {
    connectionState,
    reconnectAttempts,
    isLive,
    start,
    stop,
    subscribe,
    subscribeResync,
  }
})

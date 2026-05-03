import { authenticatedApiRequest } from '@/api/authenticated'
import { getApiBase } from '@/api/client'
import type { RealtimeTicketResponse } from '@/api/types'

const REALTIME_TICKET_SUBPROTOCOL_PREFIX = 'pragma.realtime.ticket.'

export function createRealtimeTicket(): Promise<RealtimeTicketResponse> {
  return authenticatedApiRequest<RealtimeTicketResponse>('/realtime/ticket', {
    method: 'POST',
  })
}

export function buildRealtimeWebSocketUrl(): string {
  const apiBase = getApiBase().replace(/\/$/, '')
  const httpUrl = new URL(apiBase, window.location.origin)
  const websocketUrl = new URL(httpUrl.toString())

  websocketUrl.protocol = websocketUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  websocketUrl.pathname = `${websocketUrl.pathname.replace(/\/$/, '')}/realtime/stream`
  return websocketUrl.toString()
}

export function buildRealtimeWebSocketProtocols(ticket: string): string[] {
  return [`${REALTIME_TICKET_SUBPROTOCOL_PREFIX}${ticket}`]
}

import { apiRequest, getApiBase } from '@/api/client'
import type { RealtimeTicketResponse } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

function getAccessToken(): string {
  const authStore = useAuthStore()
  if (authStore.accessToken === null) {
    throw new Error('Authentication required')
  }
  return authStore.accessToken
}

export function createRealtimeTicket(): Promise<RealtimeTicketResponse> {
  return apiRequest<RealtimeTicketResponse>('/realtime/ticket', {
    method: 'POST',
    accessToken: getAccessToken(),
  })
}

export function buildRealtimeWebSocketUrl(ticket: string): string {
  const apiBase = getApiBase().replace(/\/$/, '')
  const httpUrl = new URL(apiBase, window.location.origin)
  const websocketUrl = new URL(httpUrl.toString())

  websocketUrl.protocol = websocketUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  websocketUrl.pathname = `${websocketUrl.pathname.replace(/\/$/, '')}/realtime/stream`
  websocketUrl.searchParams.set('ticket', ticket)
  return websocketUrl.toString()
}

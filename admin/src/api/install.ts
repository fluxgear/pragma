import { apiRequest } from '@/api/client'
import type { BootstrapRequest, BootstrapResponse, InstallStatusResponse } from '@/api/types'

export function fetchInstallStatus(): Promise<InstallStatusResponse> {
  return apiRequest<InstallStatusResponse>('/install/status', {
    method: 'GET',
  })
}

export function bootstrapInstall(
  payload: BootstrapRequest,
  setupSecret?: string | null,
): Promise<BootstrapResponse> {
  const headers = new Headers()
  const trimmedSetupSecret = setupSecret?.trim() ?? ''
  if (trimmedSetupSecret.length > 0) {
    headers.set('X-Pragma-Setup-Secret', trimmedSetupSecret)
  }

  return apiRequest<BootstrapResponse>('/install/bootstrap', {
    method: 'POST',
    headers,
    body: payload,
  })
}

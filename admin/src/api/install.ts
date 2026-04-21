import { apiRequest } from '@/api/client'
import type { BootstrapRequest, BootstrapResponse, InstallStatusResponse } from '@/api/types'

export function fetchInstallStatus(): Promise<InstallStatusResponse> {
  return apiRequest<InstallStatusResponse>('/install/status', {
    method: 'GET',
  })
}

export function bootstrapInstall(payload: BootstrapRequest): Promise<BootstrapResponse> {
  return apiRequest<BootstrapResponse>('/install/bootstrap', {
    method: 'POST',
    body: payload,
  })
}

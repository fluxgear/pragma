import { authenticatedApiRequest } from '@/api/authenticated'
import type { ModuleListResponse, ModuleStateResponse, ModuleStateUpdateRequest } from '@/api/types'

export function listModules(): Promise<ModuleListResponse> {
  return authenticatedApiRequest<ModuleListResponse>('/modules')
}

export function updateModuleState(
  moduleId: string,
  payload: ModuleStateUpdateRequest,
): Promise<ModuleStateResponse> {
  return authenticatedApiRequest<ModuleStateResponse>(`/modules/${moduleId}/state`, {
    method: 'PUT',
    body: payload,
  })
}

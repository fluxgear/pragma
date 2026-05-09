import { authenticatedApiRequest } from '@/api/authenticated'
import type { RoleCreateRequest, RoleResponse, RolesAdminListResponse } from '@/api/types'

export function listRolesAdmin(): Promise<RolesAdminListResponse> {
  return authenticatedApiRequest<RolesAdminListResponse>('/roles')
}

export function createRole(payload: RoleCreateRequest): Promise<RoleResponse> {
  return authenticatedApiRequest<RoleResponse>('/roles', {
    method: 'POST',
    body: payload,
  })
}

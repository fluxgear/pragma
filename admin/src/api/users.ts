import { authenticatedApiRequest } from '@/api/authenticated'
import type {
  AdminUserCreateRequest,
  AdminUserListResponse,
  AdminUserResponse,
  AdminUserUpdateRequest,
  PasswordResetResponse,
  RoleListResponse,
  UserRoleAssignmentRequest,
} from '@/api/types'

export interface ListUsersParams {
  limit?: number
  offset?: number
}

function buildUsersQuery(params: ListUsersParams = {}): string {
  const searchParams = new URLSearchParams()

  if (params.limit !== undefined) {
    searchParams.set('limit', String(params.limit))
  }

  if (params.offset !== undefined) {
    searchParams.set('offset', String(params.offset))
  }

  const query = searchParams.toString()
  return query.length > 0 ? `/users?${query}` : '/users'
}

export function listUsers(params: ListUsersParams = {}): Promise<AdminUserListResponse> {
  return authenticatedApiRequest<AdminUserListResponse>(buildUsersQuery(params))
}

export function listRoles(): Promise<RoleListResponse> {
  return authenticatedApiRequest<RoleListResponse>('/users/roles')
}

export function createUser(payload: AdminUserCreateRequest): Promise<AdminUserResponse> {
  return authenticatedApiRequest<AdminUserResponse>('/users', {
    method: 'POST',
    body: payload,
  })
}

export function updateUser(
  userId: string,
  payload: AdminUserUpdateRequest,
): Promise<AdminUserResponse> {
  return authenticatedApiRequest<AdminUserResponse>(`/users/${userId}`, {
    method: 'PATCH',
    body: payload,
  })
}

export function replaceUserRoles(
  userId: string,
  payload: UserRoleAssignmentRequest,
): Promise<AdminUserResponse> {
  return authenticatedApiRequest<AdminUserResponse>(`/users/${userId}/roles`, {
    method: 'PUT',
    body: payload,
  })
}

export function resetUserPassword(userId: string): Promise<PasswordResetResponse> {
  return authenticatedApiRequest<PasswordResetResponse>(`/users/${userId}/password-reset`, {
    method: 'POST',
  })
}

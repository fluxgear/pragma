import { apiRequest } from '@/api/client'
import type {
  AdminUserCreateRequest,
  AdminUserListResponse,
  AdminUserResponse,
  AdminUserUpdateRequest,
  PasswordResetResponse,
  RoleListResponse,
  UserRoleAssignmentRequest,
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

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

function getAccessToken(): string {
  const authStore = useAuthStore()
  if (authStore.accessToken === null) {
    throw new Error('Authentication required')
  }
  return authStore.accessToken
}

export function listUsers(params: ListUsersParams = {}): Promise<AdminUserListResponse> {
  return apiRequest<AdminUserListResponse>(buildUsersQuery(params), {
    accessToken: getAccessToken(),
  })
}

export function listRoles(): Promise<RoleListResponse> {
  return apiRequest<RoleListResponse>('/users/roles', {
    accessToken: getAccessToken(),
  })
}

export function createUser(payload: AdminUserCreateRequest): Promise<AdminUserResponse> {
  return apiRequest<AdminUserResponse>('/users', {
    method: 'POST',
    accessToken: getAccessToken(),
    body: payload,
  })
}

export function updateUser(
  userId: string,
  payload: AdminUserUpdateRequest,
): Promise<AdminUserResponse> {
  return apiRequest<AdminUserResponse>(`/users/${userId}`, {
    method: 'PATCH',
    accessToken: getAccessToken(),
    body: payload,
  })
}

export function replaceUserRoles(
  userId: string,
  payload: UserRoleAssignmentRequest,
): Promise<AdminUserResponse> {
  return apiRequest<AdminUserResponse>(`/users/${userId}/roles`, {
    method: 'PUT',
    accessToken: getAccessToken(),
    body: payload,
  })
}

export function resetUserPassword(userId: string): Promise<PasswordResetResponse> {
  return apiRequest<PasswordResetResponse>(`/users/${userId}/password-reset`, {
    method: 'POST',
    accessToken: getAccessToken(),
  })
}

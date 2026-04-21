import { apiRequest } from '@/api/client'
import type { LoginRequest, TokenResponse, UserResponse } from '@/api/types'

export function loginUser(payload: LoginRequest): Promise<TokenResponse> {
  return apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body: payload,
  })
}

export function refreshSession(): Promise<TokenResponse> {
  return apiRequest<TokenResponse>('/auth/refresh', {
    method: 'POST',
  })
}

export function logoutUser(): Promise<void> {
  return apiRequest<void>('/auth/logout', {
    method: 'POST',
  })
}

export function getCurrentUser(accessToken: string): Promise<UserResponse> {
  return apiRequest<UserResponse>('/auth/me', {
    method: 'GET',
    accessToken,
  })
}

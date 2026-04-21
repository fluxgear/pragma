export interface CapabilityStatus {
  available: boolean
  installed: boolean
  default_version: string | null
  installed_version: string | null
}

export interface InstallStatusResponse {
  schema_ready: boolean
  is_installed: boolean
  superuser_exists: boolean
  capabilities: Record<string, CapabilityStatus>
}

export interface ReadinessResponse {
  status: string
  database: string
  schema_ready: boolean
  capabilities: Record<string, CapabilityStatus>
}

export interface UserResponse {
  id: string
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
}

export interface LoginRequest {
  identity: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: UserResponse
}

export interface BootstrapRequest {
  email: string
  username: string
  password: string
  full_name?: string | null
}

export interface BootstrapResponse {
  installed: boolean
  user: UserResponse
}

export interface ErrorResponse {
  detail: string
  code?: string
}

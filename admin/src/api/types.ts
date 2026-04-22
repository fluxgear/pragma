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

interface ContentFieldDefinitionBase {
  name: string
  label: string
  required: boolean
}

export interface TextFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'text' | 'long_text' | 'rich_text'
  min_length?: number | null
  max_length?: number | null
}

export interface IntegerFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'integer'
  minimum?: number | null
  maximum?: number | null
}

export interface NumberFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'number'
  minimum?: number | null
  maximum?: number | null
}

export interface BooleanFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'boolean'
}

export interface DateFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'date'
}

export interface DateTimeFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'datetime'
}

export interface JsonFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'json'
}

export type ContentFieldDefinition =
  | TextFieldDefinition
  | IntegerFieldDefinition
  | NumberFieldDefinition
  | BooleanFieldDefinition
  | DateFieldDefinition
  | DateTimeFieldDefinition
  | JsonFieldDefinition

export interface ContentTypeResponse {
  id: string
  name: string
  slug: string
  description: string | null
  field_definitions: ContentFieldDefinition[]
  created_by_user_id: string | null
  updated_by_user_id: string | null
  created_at: string
  updated_at: string
}

export interface ContentTypeListResponse {
  items: ContentTypeResponse[]
  total: number
  limit: number
  offset: number
}

export type ContentEntryStatus = 'draft' | 'published' | 'archived'

export interface ContentEntryResponse {
  id: string
  content_type_id: string
  content_type_slug: string
  slug: string
  status: ContentEntryStatus
  payload: Record<string, unknown>
  published_at: string | null
  created_by_user_id: string | null
  updated_by_user_id: string | null
  created_at: string
  updated_at: string
}

export interface ContentEntryListResponse {
  items: ContentEntryResponse[]
  total: number
  limit: number
  offset: number
}

export interface ContentEntryCreateRequest {
  content_type_id: string
  slug: string | null
  status: ContentEntryStatus
  payload: Record<string, unknown>
}

export interface ContentEntryUpdateRequest {
  slug: string | null
  status: ContentEntryStatus
  payload: Record<string, unknown>
}

export interface MediaSelection {
  id: string
  filename: string
  mime_type: string
  width: number | null
  height: number | null
  alt_text: string | null
  content_url: string
}

export interface MediaAssetResponse {
  id: string
  original_filename: string
  storage_key: string
  mime_type: string
  size_bytes: number
  width: number | null
  height: number | null
  alt_text: string | null
  caption: string | null
  description: string | null
  variants: Record<string, string>
  uploader_user_id: string | null
  created_at: string
  updated_at: string
  content_url: string
  is_image: boolean
  selection: MediaSelection
}

export interface MediaAssetListResponse {
  items: MediaAssetResponse[]
  total: number
  limit: number
  offset: number
}

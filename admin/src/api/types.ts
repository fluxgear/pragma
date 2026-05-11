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

export type PermissionSource = 'roles' | 'superuser'

export interface UserResponse {
  id: string
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  roles: string[]
  assigned_permissions: string[]
  effective_permissions: string[]
  has_all_permissions: boolean
  permission_source: PermissionSource
  /** Backend aliases permissions to the effective permission set for guards. */
  permissions: string[]
  force_password_change: boolean
}

export interface LoginRequest {
  identity: string
  password: string
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
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

export interface RoleResponse {
  role_key: string
  name: string
  description: string | null
  is_system: boolean
  permission_keys: string[]
}

export interface RoleListResponse {
  items: RoleResponse[]
  total: number
}

export interface PermissionDefinitionResponse {
  key: string
  name: string
  description: string | null
  domain: string
}

export interface RolesAdminListResponse {
  items: RoleResponse[]
  total: number
  permission_definitions: PermissionDefinitionResponse[]
}

export interface RoleCreateRequest {
  role_key: string
  name: string
  description?: string | null
  permission_keys: string[]
}

export interface AdminUserResponse extends UserResponse {
  last_login_at: string | null
  password_changed_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminUserListResponse {
  items: AdminUserResponse[]
  total: number
  limit: number
  offset: number
}

export interface AdminUserCreateRequest {
  email: string
  username: string
  full_name?: string | null
  password: string
  is_active: boolean
  role_keys: string[]
  force_password_change: boolean
}

export interface AdminUserUpdateRequest {
  email?: string | null
  username?: string | null
  full_name?: string | null
  is_active?: boolean | null
}

export interface UserRoleAssignmentRequest {
  role_keys: string[]
}

export interface PasswordResetResponse {
  temporary_password: string
}

interface ContentFieldDefinitionBase {
  name: string
  label: string
  required: boolean
  help_text?: string | null
  default_value?: unknown
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

export interface BlockDocumentFieldDefinition extends ContentFieldDefinitionBase {
  kind: 'block_document'
}

export interface BlockNode {
  type: string
  props: Record<string, unknown>
  settings: Record<string, unknown>
  children: BlockNode[]
}

export interface BlockDocument {
  version: 1
  root: BlockNode
}

export type ContentFieldDefinition =
  | TextFieldDefinition
  | IntegerFieldDefinition
  | NumberFieldDefinition
  | BooleanFieldDefinition
  | DateFieldDefinition
  | DateTimeFieldDefinition
  | JsonFieldDefinition
  | BlockDocumentFieldDefinition

export interface ContentTypeResponse {
  id: string
  name: string
  slug: string
  description: string | null
  field_definitions: ContentFieldDefinition[]
  entry_count: number
  can_delete: boolean
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

export interface ContentTypeCreateRequest {
  name: string
  slug?: string | null
  description?: string | null
  field_definitions: ContentFieldDefinition[]
}

export interface ContentTypeUpdateRequest {
  name: string
  slug?: string | null
  description?: string | null
  field_definitions: ContentFieldDefinition[]
}

export type ContentEntryStatus = 'draft' | 'published' | 'archived'

export type ContentSeoRobots = 'index' | 'noindex'

export interface ContentEntrySeoMetadata {
  title: string | null
  description: string | null
  canonical_url: string | null
  robots: ContentSeoRobots
  og_title: string | null
  og_description: string | null
  og_image: string | null
}

export interface ContentEntryResponse {
  id: string
  content_type_id: string
  content_type_slug: string
  slug: string
  status: ContentEntryStatus
  payload: Record<string, unknown>
  seo_metadata: ContentEntrySeoMetadata
  version: number
  revision_number: number | null
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
  seo_metadata?: ContentEntrySeoMetadata
}

export interface ContentEntryUpdateRequest {
  slug: string | null
  status: ContentEntryStatus
  payload: Record<string, unknown>
  seo_metadata?: ContentEntrySeoMetadata
  expected_version?: number | null
}

export type ContentEntryRevisionAction = 'create' | 'update' | 'publish' | 'unpublish' | 'restore'

export interface ContentEntryRevisionResponse {
  id: string
  entry_id: string
  revision_number: number
  action: ContentEntryRevisionAction
  slug: string
  status: ContentEntryStatus
  payload: Record<string, unknown>
  seo_metadata: ContentEntrySeoMetadata
  published_at: string | null
  created_by_user_id: string | null
  created_at: string
  restore_source_revision_id: string | null
}

export interface ContentEntryRevisionListResponse {
  items: ContentEntryRevisionResponse[]
}

export interface ContentEntryWorkflowRequest {
  expected_version?: number | null
}

export type ContentEntryTransitionRequest = ContentEntryWorkflowRequest

export type ContentEntryRevisionRestoreRequest = ContentEntryWorkflowRequest

export interface ContentEntryPreviewResponse {
  entry_id: string
  token: string
  preview_url: string
  expires_at: string
}


export interface ContentEntryAutosaveRequest {
  base_version: number
  slug: string | null
  payload: Record<string, unknown>
  seo_metadata: ContentEntrySeoMetadata
}

export interface ContentEntryAutosaveResponse {
  entry_id: string
  user_id: string
  base_version: number
  current_version: number
  is_stale: boolean
  slug: string
  payload: Record<string, unknown>
  seo_metadata: ContentEntrySeoMetadata
  updated_at: string
}

export type ContentEntryActivityAction =
  | 'create'
  | 'update'
  | 'autosave'
  | 'publish'
  | 'unpublish'
  | 'restore'
  | 'preview'
  | 'delete'
  | 'schedule_set'
  | 'schedule_cancel'
  | 'schedule_execute'
  | 'schedule_fail'

export interface ContentEntryActivityResponse {
  id: string
  entry_id: string
  content_type_id: string | null
  entry_slug: string | null
  entry_version: number | null
  action: ContentEntryActivityAction
  actor_user_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface ContentEntryActivityListResponse {
  items: ContentEntryActivityResponse[]
  total: number
  limit: number
  offset: number
}

export interface ContentEntryScheduleRequest {
  expected_version: number
  publish_at?: string | null
  unpublish_at?: string | null
}

export type ContentEntryScheduleAction = 'publish' | 'unpublish'
export type ContentEntryScheduleState = 'pending' | 'executed' | 'cancelled' | 'failed'

export interface ContentEntryScheduleItemResponse {
  id: string
  entry_id: string
  action: ContentEntryScheduleAction
  run_at: string
  requested_entry_version: number
  requested_by_user_id: string | null
  state: ContentEntryScheduleState
  created_at: string
  updated_at: string
  executed_at: string | null
  cancelled_at: string | null
  failure_code: string | null
  failure_detail: string | null
}

export interface ContentEntryScheduleResponse {
  entry_id: string
  publish: ContentEntryScheduleItemResponse | null
  unpublish: ContentEntryScheduleItemResponse | null
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
  metadata: Record<string, unknown>
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

export type AIProviderKind = 'voyage' | 'openai' | 'openai_compatible'

export type AIProviderApiMode = 'responses' | 'chat_completions'

export type AIProviderAuthMode = 'api_key' | 'oauth'

export type AICapability =
  | 'text_generation'
  | 'editor_assist'
  | 'seo_assist'
  | 'embeddings'
  | 'image_generation'
  | 'streaming'
  | 'tool_calling'

export interface AIProviderSecretStatus {
  configured: boolean
  auth_mode: AIProviderAuthMode
  last4: string | null
  updated_at: string | null
}

export interface AIProviderSettingsResponse {
  enabled: boolean
  provider: AIProviderKind | null
  display_name: string | null
  api_mode: AIProviderApiMode
  auth_mode: AIProviderAuthMode
  base_url: string | null
  embedding_model: string | null
  embedding_dimensions: number | null
  generation_model: string | null
  capabilities: AICapability[]
  request_timeout_seconds: number | null
  api_key_configured: boolean
  api_key_status: AIProviderSecretStatus
  oauth_connected: boolean
  last_test_status: string | null
  last_tested_at: string | null
  updated_at: string | null
  embeddings_rebuild_required: boolean
}

export interface AIProviderSettingsUpdateRequest {
  enabled: boolean
  provider: AIProviderKind | null
  display_name?: string | null
  api_mode: AIProviderApiMode
  auth_mode: AIProviderAuthMode
  base_url: string | null
  embedding_model: string | null
  embedding_dimensions: number | null
  generation_model?: string | null
  text_generation_enabled: boolean
  editor_assist_enabled: boolean
  seo_assist_enabled: boolean
  request_timeout_seconds: number
  api_key?: string | null
  retain_existing_api_key?: boolean
}

export interface AIProviderTestRequest {
  query_text?: string
}

export interface AIProviderTestResponse {
  provider: AIProviderKind
  embedding_model: string
  embedding_dimensions: number
}

export type AIGenerationScope = 'editor' | 'seo'

export type AIGenerationMessageRole = 'system' | 'developer' | 'user' | 'assistant'

export interface AIGenerationMessage {
  role: AIGenerationMessageRole
  content: string
}

export interface AIGenerationRequest {
  scope: AIGenerationScope
  input: string
  instructions?: string | null
  messages?: AIGenerationMessage[]
  model?: string | null
  temperature?: number | null
  max_output_tokens?: number | null
}

export interface AIGenerationResponse {
  provider: AIProviderKind
  api_mode: AIProviderApiMode
  model: string
  text: string
  finish_reason: string | null
  usage: Record<string, number> | null
}

export interface AIOAuthStatusResponse {
  provider: AIProviderKind | null
  supported: boolean
  connected: boolean
  auth_mode: AIProviderAuthMode | null
  reason: string
}

export interface AIOAuthStartResponse {
  supported: boolean
  authorization_url: string | null
  state: string | null
  reason: string
}

export interface AISearchEmbeddingRebuildRequest {
  batch_size: number
  max_documents: number
  content_type_slug?: string | null
  force: boolean
}

export interface AISearchEmbeddingRebuildResponse {
  attempted: number
  embedded: number
  failed: number
  failed_entry_ids: string[]
}

export type ThemeTypographyPreset = 'system' | 'serif' | 'editorial'

export type ThemeSpacingScale = 'compact' | 'comfortable' | 'spacious'

export type ThemeRadiusScale = 'none' | 'small' | 'medium' | 'large'

export interface ThemeDesignSettings {
  primary_color: string
  accent_color: string
  background_color: string
  text_color: string
  typography_preset: ThemeTypographyPreset
  spacing_scale: ThemeSpacingScale
  radius_scale: ThemeRadiusScale
}

export type ThemeDesignSettingsUpdate = Partial<ThemeDesignSettings>

export interface ThemeManifestResponse {
  id: string
  name: string
  version: string
  description: string | null
  author: string | null
  active: boolean
  default: boolean
  current: boolean
  available: boolean
}

export interface ThemeSettingsResponse {
  active_theme_id: string
  default_theme_id: string
  current_theme_id: string | null
  persisted_active_theme_id: string | null
  design_settings: ThemeDesignSettings
  design_warnings: string[]
  themes: ThemeManifestResponse[]
}

export interface ThemeSettingsUpdateRequest {
  active_theme_id?: string | null
  design_settings?: ThemeDesignSettingsUpdate | null
}

export interface ModuleStateResponse {
  module_id: string
  name: string
  version: string
  order: number
  enabled: boolean
  loaded: boolean
  hooks: string[]
  error_code: string | null
}

export interface ModuleListResponse {
  items: ModuleStateResponse[]
  total: number
}

export interface ModuleStateUpdateRequest {
  enabled: boolean
}


export interface RealtimeTicketResponse {
  ticket: string
  expires_at: string
}

export type RealtimeEventType =
  | 'content.entry.created'
  | 'content.entry.updated'
  | 'content.entry.deleted'
  | 'realtime.resync_required'

export interface RealtimeEventEnvelope {
  version: 1
  id: string
  type: RealtimeEventType
  resource: string
  action: string
  resource_id?: string
  occurred_at: string
  actor_id?: string
  data: Record<string, unknown>
}

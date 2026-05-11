import { authenticatedApiRequest } from '@/api/authenticated'

export type NavigationLinkType = 'content_entry' | 'custom_url'

export interface NavigationMenuItemRequest {
  label: string
  link_type: NavigationLinkType
  content_entry_id?: string | null
  url?: string | null
  enabled?: boolean
  children?: NavigationMenuItemRequest[]
}

export interface NavigationMenuReplaceRequest {
  items: NavigationMenuItemRequest[]
}

export interface NavigationMenuItemResponse {
  id: string
  parent_item_id: string | null
  position: number
  label: string
  link_type: NavigationLinkType
  enabled: boolean
  content_entry_id: string | null
  url: string | null
  href: string | null
  content_type_slug: string | null
  entry_slug: string | null
  entry_status: string | null
  children: NavigationMenuItemResponse[]
}

export interface NavigationWarningResponse {
  code: string
  detail: string
  item_position: number
  item_label: string
  content_entry_id: string | null
}

export interface NavigationMenuResponse {
  key: 'primary' | string
  items: NavigationMenuItemResponse[]
  warnings: NavigationWarningResponse[]
}

export interface NavigationContentOption {
  id: string
  label: string
  content_type_slug: string
  slug: string
  status: string
  href: string
}

export interface NavigationContentOptionListResponse {
  items: NavigationContentOption[]
  total: number
  limit: number
  offset: number
}

export function getPrimaryNavigationMenu(): Promise<NavigationMenuResponse> {
  return authenticatedApiRequest<NavigationMenuResponse>('/navigation/primary')
}

export function replacePrimaryNavigationMenu(
  payload: NavigationMenuReplaceRequest,
): Promise<NavigationMenuResponse> {
  return authenticatedApiRequest<NavigationMenuResponse>('/navigation/primary', {
    method: 'PUT',
    body: payload,
  })
}

export function listNavigationContentOptions(
  limit = 100,
  offset = 0,
): Promise<NavigationContentOptionListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  return authenticatedApiRequest<NavigationContentOptionListResponse>(
    `/navigation/content-options?${params.toString()}`,
  )
}

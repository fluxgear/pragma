import { authenticatedApiRequest } from '@/api/authenticated'
import type { ThemeSettingsResponse, ThemeSettingsUpdateRequest } from '@/api/types'

export function listThemes(): Promise<ThemeSettingsResponse> {
  return authenticatedApiRequest<ThemeSettingsResponse>('/themes')
}

export function updateThemeSettings(
  payload: ThemeSettingsUpdateRequest,
): Promise<ThemeSettingsResponse> {
  return authenticatedApiRequest<ThemeSettingsResponse>('/themes/settings', {
    method: 'PUT',
    body: payload,
  })
}

export function resetThemeSettings(): Promise<ThemeSettingsResponse> {
  return authenticatedApiRequest<ThemeSettingsResponse>('/themes/settings/reset', {
    method: 'POST',
  })
}

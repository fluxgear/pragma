import { apiRequest } from '@/api/client'
import type {
  AIProviderSettingsResponse,
  AIProviderSettingsUpdateRequest,
  AIProviderTestRequest,
  AIProviderTestResponse,
  AISearchEmbeddingRebuildRequest,
  AISearchEmbeddingRebuildResponse,
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const DEFAULT_AI_QUERY_TEXT = 'semantic search healthcheck'

function getAccessToken(): string {
  const authStore = useAuthStore()
  if (authStore.accessToken === null) {
    throw new Error('Authentication required')
  }
  return authStore.accessToken
}

export function getAiSettings(): Promise<AIProviderSettingsResponse> {
  return apiRequest<AIProviderSettingsResponse>('/ai/settings', {
    accessToken: getAccessToken(),
  })
}

export function updateAiSettings(
  payload: AIProviderSettingsUpdateRequest,
): Promise<AIProviderSettingsResponse> {
  return apiRequest<AIProviderSettingsResponse>('/ai/settings', {
    accessToken: getAccessToken(),
    method: 'PUT',
    body: payload,
  })
}

export function testAiProvider(
  payload: AIProviderTestRequest = { query_text: DEFAULT_AI_QUERY_TEXT },
): Promise<AIProviderTestResponse> {
  return apiRequest<AIProviderTestResponse>('/ai/settings/test', {
    accessToken: getAccessToken(),
    method: 'POST',
    body: payload,
  })
}

export function rebuildAiEmbeddings(
  payload: AISearchEmbeddingRebuildRequest,
): Promise<AISearchEmbeddingRebuildResponse> {
  return apiRequest<AISearchEmbeddingRebuildResponse>('/ai/search/rebuild', {
    accessToken: getAccessToken(),
    method: 'POST',
    body: payload,
  })
}

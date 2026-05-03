import { authenticatedApiRequest } from '@/api/authenticated'
import type {
  AIProviderSettingsResponse,
  AIProviderSettingsUpdateRequest,
  AIProviderTestRequest,
  AIProviderTestResponse,
  AISearchEmbeddingRebuildRequest,
  AISearchEmbeddingRebuildResponse,
} from '@/api/types'

const DEFAULT_AI_QUERY_TEXT = 'semantic search healthcheck'

export function getAiSettings(): Promise<AIProviderSettingsResponse> {
  return authenticatedApiRequest<AIProviderSettingsResponse>('/ai/settings')
}

export function updateAiSettings(
  payload: AIProviderSettingsUpdateRequest,
): Promise<AIProviderSettingsResponse> {
  return authenticatedApiRequest<AIProviderSettingsResponse>('/ai/settings', {
    method: 'PUT',
    body: payload,
  })
}

export function testAiProvider(
  payload: AIProviderTestRequest = { query_text: DEFAULT_AI_QUERY_TEXT },
): Promise<AIProviderTestResponse> {
  return authenticatedApiRequest<AIProviderTestResponse>('/ai/settings/test', {
    method: 'POST',
    body: payload,
  })
}

export function rebuildAiEmbeddings(
  payload: AISearchEmbeddingRebuildRequest,
): Promise<AISearchEmbeddingRebuildResponse> {
  return authenticatedApiRequest<AISearchEmbeddingRebuildResponse>('/ai/search/rebuild', {
    method: 'POST',
    body: payload,
  })
}

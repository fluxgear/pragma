import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { getAiSettings, rebuildAiEmbeddings, testAiProvider, updateAiSettings } from '@/api/ai'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

const settingsResponse = {
  enabled: true,
  provider: 'voyage',
  base_url: 'https://api.voyageai.com/v1',
  embedding_model: 'voyage-3.5-lite',
  embedding_dimensions: 1024,
  request_timeout_seconds: 8,
  api_key_configured: true,
  updated_at: '2026-04-26T12:00:00Z',
  embeddings_rebuild_required: false,
}

const testResponse = {
  provider: 'voyage',
  embedding_model: 'voyage-3.5-lite',
  embedding_dimensions: 3,
}

const rebuildResponse = {
  attempted: 20,
  embedded: 20,
  failed: 0,
  failed_entry_ids: [],
}

describe('AI API helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = accessToken
  })

  it('fetches AI settings with the bearer token', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(settingsResponse)

    await getAiSettings()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/ai/settings', {
      accessToken,
    })
  })

  it('updates AI settings with the provided payload', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(settingsResponse)

    const requestPayload = {
      enabled: true,
      provider: 'voyage',
      base_url: 'https://api.voyageai.com/v1',
      embedding_model: 'voyage-3.5-lite',
      embedding_dimensions: 1024,
      request_timeout_seconds: 10,
      api_key: 'secret',
      retain_existing_api_key: true,
    }

    await updateAiSettings(requestPayload)

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/ai/settings', {
      accessToken,
      method: 'PUT',
      body: requestPayload,
    })
  })

  it('tests AI provider with the default query payload', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(testResponse)

    await testAiProvider()

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/ai/settings/test', {
      accessToken,
      method: 'POST',
      body: {
        query_text: 'semantic search healthcheck',
      },
    })
  })

  it('supports custom provider test payloads', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(testResponse)

    await testAiProvider({ query_text: 'custom healthcheck' })

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/ai/settings/test', {
      accessToken,
      method: 'POST',
      body: {
        query_text: 'custom healthcheck',
      },
    })
  })

  it('requests an embedding rebuild with provided parameters', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(rebuildResponse)

    const requestPayload = {
      batch_size: 25,
      max_documents: 100,
      force: true,
    }

    await rebuildAiEmbeddings(requestPayload)

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/ai/search/rebuild', {
      accessToken,
      method: 'POST',
      body: requestPayload,
    })
  })

  it('fails fast when no session access token is available', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    await expect(getAiSettings()).rejects.toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

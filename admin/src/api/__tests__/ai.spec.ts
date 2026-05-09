import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  completeAiOAuthCallback,
  disconnectAiOAuth,
  generateAiText,
  getAiOAuthStatus,
  getAiSettings,
  rebuildAiEmbeddings,
  startAiOAuth,
  testAiProvider,
  updateAiSettings,
} from '@/api/ai'
import { useAuthStore } from '@/stores/auth'

const apiClientMocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}))

vi.mock('@/api/client', () => apiClientMocks)

const accessToken = 'token-123'

const settingsResponse = {
  enabled: true,
  provider: 'openai_compatible',
  display_name: 'Acme AI',
  api_mode: 'chat_completions',
  auth_mode: 'api_key',
  base_url: 'https://api.example.com/v1',
  embedding_model: 'text-embedding-3-small',
  embedding_dimensions: 1024,
  generation_model: 'gpt-5-mini',
  capabilities: ['embeddings', 'text_generation', 'editor_assist'],
  request_timeout_seconds: 8,
  api_key_configured: true,
  api_key_status: {
    configured: true,
    auth_mode: 'api_key',
    last4: '1234',
    updated_at: '2026-05-07T00:00:00Z',
  },
  oauth_connected: false,
  last_test_status: 'passed',
  last_tested_at: '2026-05-07T00:01:00Z',
  updated_at: '2026-05-07T00:00:00Z',
  embeddings_rebuild_required: false,
}

const testResponse = {
  provider: 'openai_compatible',
  embedding_model: 'text-embedding-3-small',
  embedding_dimensions: 3,
}

const generationResponse = {
  provider: 'openai_compatible',
  api_mode: 'chat_completions',
  model: 'gpt-5-mini',
  text: 'Draft heading',
  finish_reason: 'stop',
  usage: { input_tokens: 12, output_tokens: 4 },
}

const oauthStatusResponse = {
  provider: 'openai_compatible',
  supported: false,
  connected: false,
  auth_mode: 'api_key',
  reason: 'AI OAuth is unsupported until provider OAuth metadata is configured',
}

const oauthStartResponse = {
  supported: false,
  authorization_url: null,
  state: null,
  reason: 'AI OAuth is unsupported until provider OAuth metadata is configured',
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

  it('updates expanded AI settings with the provided payload', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(settingsResponse)

    const requestPayload = {
      enabled: true,
      provider: 'openai_compatible',
      display_name: 'Acme AI',
      api_mode: 'chat_completions',
      auth_mode: 'api_key',
      base_url: 'https://api.example.com/v1',
      embedding_model: 'text-embedding-3-small',
      embedding_dimensions: 1024,
      generation_model: 'gpt-5-mini',
      text_generation_enabled: true,
      editor_assist_enabled: true,
      seo_assist_enabled: false,
      request_timeout_seconds: 10,
      api_key: 'secret',
      retain_existing_api_key: false,
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

  it('sends generation smoke requests only to the backend generation route', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(generationResponse)

    const requestPayload = {
      scope: 'editor',
      input: 'Draft a page heading',
      instructions: 'Return one short draft.',
      model: 'gpt-5-mini',
      max_output_tokens: 128,
    }

    await generateAiText(requestPayload)

    expect(apiClientMocks.apiRequest).toHaveBeenCalledWith('/ai/generate', {
      accessToken,
      method: 'POST',
      body: requestPayload,
    })
  })

  it('uses backend OAuth status, start, callback, and disconnect routes', async () => {
    apiClientMocks.apiRequest
      .mockResolvedValueOnce(oauthStatusResponse)
      .mockResolvedValueOnce(oauthStartResponse)
      .mockResolvedValueOnce(oauthStatusResponse)
      .mockResolvedValueOnce(oauthStatusResponse)

    await getAiOAuthStatus()
    await startAiOAuth()
    await completeAiOAuthCallback()
    await disconnectAiOAuth()

    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(1, '/ai/oauth/status', {
      accessToken,
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(2, '/ai/oauth/start', {
      accessToken,
      method: 'POST',
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(3, '/ai/oauth/callback', {
      accessToken,
    })
    expect(apiClientMocks.apiRequest).toHaveBeenNthCalledWith(4, '/ai/oauth', {
      accessToken,
      method: 'DELETE',
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

  it('never calls configured provider URLs directly from the browser helper layer', async () => {
    apiClientMocks.apiRequest.mockResolvedValue(settingsResponse)

    await updateAiSettings({
      enabled: true,
      provider: 'openai_compatible',
      display_name: null,
      api_mode: 'chat_completions',
      auth_mode: 'api_key',
      base_url: 'https://provider.example.com/v1',
      embedding_model: 'text-embedding-3-small',
      embedding_dimensions: 1024,
      generation_model: 'gpt-5-mini',
      text_generation_enabled: true,
      editor_assist_enabled: true,
      seo_assist_enabled: false,
      request_timeout_seconds: 10,
      retain_existing_api_key: true,
    })

    const requestedPaths = apiClientMocks.apiRequest.mock.calls.map(([path]) => path)
    expect(requestedPaths).toEqual(['/ai/settings'])
    expect(requestedPaths.every((path) => String(path).startsWith('/ai/'))).toBe(true)
  })

  it('fails fast when no session access token is available', async () => {
    const authStore = useAuthStore()
    authStore.accessToken = null

    await expect(getAiSettings()).rejects.toThrowError(new Error('Authentication required'))
    expect(apiClientMocks.apiRequest).not.toHaveBeenCalled()
  })
})

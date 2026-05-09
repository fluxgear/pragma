import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { useAuthStore } from '@/stores/auth'
import AiSettingsView from '@/views/AiSettingsView.vue'

const aiApiMocks = vi.hoisted(() => ({
  disconnectAiOAuth: vi.fn(),
  generateAiText: vi.fn(),
  getAiOAuthStatus: vi.fn(),
  getAiSettings: vi.fn(),
  rebuildAiEmbeddings: vi.fn(),
  startAiOAuth: vi.fn(),
  testAiProvider: vi.fn(),
  updateAiSettings: vi.fn(),
}))

vi.mock('@/api/ai', () => aiApiMocks)

if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

class ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

vi.stubGlobal('ResizeObserver', ResizeObserver)

const accessToken = 'token-123'
const aiPermissions = ['ai.settings.manage', 'ai.oauth.manage', 'ai.editor_assist', 'ai.seo_assist']

const settingsPayload = {
  enabled: true,
  provider: 'openai_compatible',
  display_name: 'Acme AI',
  api_mode: 'chat_completions',
  auth_mode: 'api_key',
  base_url: 'https://api.example.com/v1',
  embedding_model: 'text-embedding-3-small',
  embedding_dimensions: 2,
  generation_model: 'gpt-5-mini',
  capabilities: ['embeddings', 'text_generation', 'editor_assist'],
  request_timeout_seconds: 12,
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

const rebuildRequiredSettingsPayload = {
  ...settingsPayload,
  embeddings_rebuild_required: true,
}

const disabledSettingsPayload = {
  enabled: false,
  provider: null,
  display_name: null,
  api_mode: 'chat_completions',
  auth_mode: 'api_key',
  base_url: null,
  embedding_model: null,
  embedding_dimensions: null,
  generation_model: null,
  capabilities: [],
  request_timeout_seconds: null,
  api_key_configured: false,
  api_key_status: {
    configured: false,
    auth_mode: 'api_key',
    last4: null,
    updated_at: null,
  },
  oauth_connected: false,
  last_test_status: null,
  last_tested_at: null,
  updated_at: null,
  embeddings_rebuild_required: false,
}

const oauthUnsupportedPayload = {
  provider: 'openai_compatible',
  supported: false,
  connected: false,
  auth_mode: 'api_key',
  reason: 'AI OAuth is unsupported until provider OAuth metadata is configured',
}

async function mountView(isSuperuser = true) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = accessToken
  authStore.user = {
    id: 'user-1',
    email: 'admin@example.com',
    username: 'admin',
    full_name: 'Admin User',
    is_active: true,
    is_superuser: isSuperuser,
    roles: isSuperuser ? ['administrator'] : ['viewer'],
    assigned_permissions: isSuperuser ? aiPermissions : [],
    effective_permissions: isSuperuser ? aiPermissions : [],
    has_all_permissions: isSuperuser,
    permission_source: isSuperuser ? 'superuser' : 'roles',
    permissions: isSuperuser ? aiPermissions : [],
    force_password_change: false,
  }

  const wrapper = mount(AiSettingsView, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper }
}

describe('AiSettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    aiApiMocks.getAiSettings.mockResolvedValue(settingsPayload)
    aiApiMocks.getAiOAuthStatus.mockResolvedValue(oauthUnsupportedPayload)
    aiApiMocks.startAiOAuth.mockResolvedValue({
      supported: false,
      authorization_url: null,
      state: null,
      reason: oauthUnsupportedPayload.reason,
    })
    aiApiMocks.disconnectAiOAuth.mockResolvedValue(oauthUnsupportedPayload)
    aiApiMocks.generateAiText.mockResolvedValue({
      provider: 'openai_compatible',
      api_mode: 'chat_completions',
      model: 'gpt-5-mini',
      text: 'Draft heading',
      finish_reason: 'stop',
      usage: { input_tokens: 10, output_tokens: 2 },
    })
    aiApiMocks.testAiProvider.mockResolvedValue({
      provider: 'openai_compatible',
      embedding_model: 'text-embedding-3-small',
      embedding_dimensions: 2,
    })
    aiApiMocks.updateAiSettings.mockResolvedValue(settingsPayload)
    aiApiMocks.rebuildAiEmbeddings.mockResolvedValue({
      attempted: 20,
      embedded: 20,
      failed: 0,
      failed_entry_ids: [],
    })
  })

  it('loads expanded AI settings, secret status, and OAuth unsupported status', async () => {
    const { wrapper } = await mountView()

    expect(aiApiMocks.getAiSettings).toHaveBeenCalledTimes(1)
    expect(aiApiMocks.getAiOAuthStatus).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('AI settings')
    expect(wrapper.text()).toContain('openai_compatible')
    expect(wrapper.text()).toContain('chat_completions')
    expect(wrapper.text()).toContain('gpt-5-mini')
    expect(wrapper.text()).toContain('Configured · ending 1234')
    expect(wrapper.text()).toContain(oauthUnsupportedPayload.reason)
  })

  it('saves provider/API/auth mode and generation capability settings then runs a forced rebuild when required', async () => {
    aiApiMocks.updateAiSettings.mockResolvedValue(rebuildRequiredSettingsPayload)

    const { wrapper } = await mountView()

    await wrapper.get('#ai-api-mode').setValue('responses')
    await wrapper.get('#ai-base-url').setValue('https://api.custom.example.com/v1')
    await wrapper.get('#ai-embedding-model').setValue('text-embedding-custom')
    await wrapper.get('#ai-generation-model').setValue('gpt-5-custom')
    await wrapper.get('#ai-cap-seo-assist').setValue(true)
    await wrapper.get('#ai-save-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.updateAiSettings).toHaveBeenCalledWith({
      enabled: true,
      provider: 'openai_compatible',
      display_name: 'Acme AI',
      api_mode: 'responses',
      auth_mode: 'api_key',
      base_url: 'https://api.custom.example.com/v1',
      embedding_model: 'text-embedding-custom',
      embedding_dimensions: 2,
      generation_model: 'gpt-5-custom',
      text_generation_enabled: true,
      editor_assist_enabled: true,
      seo_assist_enabled: true,
      request_timeout_seconds: 12,
      retain_existing_api_key: true,
    })
    expect(aiApiMocks.rebuildAiEmbeddings).toHaveBeenCalledWith({
      batch_size: 20,
      max_documents: 200,
      force: true,
    })
    expect(wrapper.text()).toContain('AI settings saved successfully. Rebuild started: 20/20 embedded, 0 failed')
  })

  it('saves a new API token without redisplaying the raw token', async () => {
    const updatedSettings = {
      ...settingsPayload,
      api_key_status: {
        configured: true,
        auth_mode: 'api_key',
        last4: 'wxyz',
        updated_at: '2026-05-07T00:02:00Z',
      },
    }
    aiApiMocks.updateAiSettings.mockResolvedValue(updatedSettings)

    const { wrapper } = await mountView()
    const secret = 'sk-live-secret-value'

    await wrapper.get('#ai-api-key').setValue(secret)
    await wrapper.get('#ai-save-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.updateAiSettings).toHaveBeenCalledWith(expect.objectContaining({
      api_key: secret,
      retain_existing_api_key: true,
    }))
    expect((wrapper.get('#ai-api-key').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).not.toContain(secret)
    expect(wrapper.text()).toContain('Configured · ending wxyz')
  })

  it('allows clearing a retained API token through the settings API', async () => {
    aiApiMocks.updateAiSettings.mockResolvedValue(disabledSettingsPayload)

    const { wrapper } = await mountView()

    await wrapper.get('#ai-clear-key-btn').trigger('click')
    await wrapper.get('#ai-save-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.updateAiSettings).toHaveBeenCalledWith(expect.objectContaining({
      api_key: null,
      retain_existing_api_key: false,
    }))
  })

  it('shows OAuth status and keeps unsupported connect/disconnect actions disabled', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('OAuth status')
    expect(wrapper.text()).toContain('Unsupported')
    expect(wrapper.get('#ai-oauth-connect-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#ai-oauth-disconnect-btn').attributes('disabled')).toBeDefined()
  })

  it('tests provider connectivity and shows test result feedback', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('#ai-test-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.testAiProvider).toHaveBeenCalledWith()
    expect(wrapper.text()).toContain('Provider test passed: openai_compatible (text-embedding-3-small, 2 dimensions)')
  })

  it('runs a backend generation smoke test and displays draft-only output', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('#ai-generation-input').setValue('Draft a homepage heading')
    await wrapper.get('#ai-generate-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.generateAiText).toHaveBeenCalledWith(expect.objectContaining({
      scope: 'editor',
      input: 'Draft a homepage heading',
      model: 'gpt-5-mini',
      max_output_tokens: 128,
    }))
    expect(wrapper.text()).toContain('Generation smoke test completed through openai_compatible chat_completions.')
    expect(wrapper.text()).toContain('Draft heading')
  })

  it('runs embedding rebuild and shows rebuild feedback', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('#ai-rebuild-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.rebuildAiEmbeddings).toHaveBeenCalledWith({
      batch_size: 20,
      max_documents: 200,
      force: false,
    })
    expect(wrapper.text()).toContain('Rebuild batch complete: 20/20 embedded, 0 failed')
  })

  it('keeps save disabled after a settings load failure', async () => {
    aiApiMocks.getAiSettings.mockRejectedValue(new Error('Unable to load AI settings'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Unable to load AI settings')
    expect(wrapper.get('#ai-save-btn').attributes('disabled')).toBeDefined()

    await wrapper.get('#ai-save-btn').trigger('click')
    expect(aiApiMocks.updateAiSettings).not.toHaveBeenCalled()
  })

  it('does not load or expose mutable actions to users missing ai.settings.manage', async () => {
    const { wrapper } = await mountView(false)

    expect(aiApiMocks.getAiSettings).not.toHaveBeenCalled()
    expect(aiApiMocks.getAiOAuthStatus).not.toHaveBeenCalled()
    expect(wrapper.get('#ai-save-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#ai-test-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#ai-rebuild-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#ai-generate-btn').attributes('disabled')).toBeDefined()

    await wrapper.get('#ai-save-btn').trigger('click')
    expect(aiApiMocks.updateAiSettings).not.toHaveBeenCalled()
  })
})

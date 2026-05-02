import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { useAuthStore } from '@/stores/auth'
import AiSettingsView from '@/views/AiSettingsView.vue'

const aiApiMocks = vi.hoisted(() => ({
  getAiSettings: vi.fn(),
  rebuildAiEmbeddings: vi.fn(),
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

const settingsPayload = {
  enabled: true,
  provider: 'voyage',
  base_url: 'https://api.voyageai.com/v1',
  embedding_model: 'voyage-3.5-lite',
  embedding_dimensions: 2,
  request_timeout_seconds: 12,
  api_key_configured: true,
  updated_at: '2026-04-26T12:00:00Z',
  embeddings_rebuild_required: false,
}

const rebuildRequiredSettingsPayload = {
  ...settingsPayload,
  embeddings_rebuild_required: true,
}

const disabledSettingsPayload = {
  enabled: false,
  provider: null,
  base_url: null,
  embedding_model: null,
  embedding_dimensions: null,
  request_timeout_seconds: null,
  api_key_configured: false,
  updated_at: null,
  embeddings_rebuild_required: false,
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
    permissions: isSuperuser ? ['ai.settings.manage'] : [],
    force_password_change: false,
  }

  const wrapper = mount(AiSettingsView, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()

  return { wrapper }
}

describe('AiSettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    aiApiMocks.getAiSettings.mockResolvedValue(settingsPayload)
    aiApiMocks.testAiProvider.mockResolvedValue({
      provider: 'voyage',
      embedding_model: 'voyage-3.5-lite',
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

  it('loads current AI settings and shows provider status', async () => {
    const { wrapper } = await mountView()

    expect(aiApiMocks.getAiSettings).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('AI settings')
    expect(wrapper.text()).toContain('voyage')
    expect(wrapper.text()).toContain('Current provider status')
    expect(wrapper.text()).toContain('2')
  })

  it('saves updated settings and runs a forced rebuild when required', async () => {
    aiApiMocks.updateAiSettings.mockResolvedValue(rebuildRequiredSettingsPayload)

    const { wrapper } = await mountView()

    await wrapper.get('#ai-base-url').setValue('https://api.custom.example.com/v1')
    await wrapper.get('#ai-embedding-model').setValue('voyage-3.5-pro')
    await wrapper.get('#ai-save-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.updateAiSettings).toHaveBeenCalledWith({
      enabled: true,
      provider: 'voyage',
      base_url: 'https://api.custom.example.com/v1',
      embedding_model: 'voyage-3.5-pro',
      embedding_dimensions: 2,
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

  it('allows disabled settings to save without provider metadata', async () => {
    aiApiMocks.getAiSettings.mockResolvedValue(disabledSettingsPayload)
    aiApiMocks.updateAiSettings.mockResolvedValue(disabledSettingsPayload)

    const { wrapper } = await mountView()

    await wrapper.get('#ai-save-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.updateAiSettings).toHaveBeenCalledWith({
      enabled: false,
      provider: null,
      base_url: null,
      embedding_model: null,
      embedding_dimensions: null,
      request_timeout_seconds: 15,
      api_key: null,
      retain_existing_api_key: false,
    })
  })

  it('keeps save disabled after a settings load failure', async () => {
    aiApiMocks.getAiSettings.mockRejectedValue(new Error('Unable to load AI settings'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Unable to load AI settings')
    expect(wrapper.get('#ai-save-btn').attributes('disabled')).toBeDefined()

    await wrapper.get('#ai-save-btn').trigger('click')
    expect(aiApiMocks.updateAiSettings).not.toHaveBeenCalled()
  })

  it('tests provider connectivity and shows test result feedback', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('#ai-test-btn').trigger('click')
    await flushPromises()

    expect(aiApiMocks.testAiProvider).toHaveBeenCalledWith()
    expect(wrapper.text()).toContain('Provider test passed: voyage (voyage-3.5-lite, 2 dimensions)')
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

  it('does not load or expose save/test/rebuild actions to non-superusers', async () => {
    const { wrapper } = await mountView(false)

    expect(aiApiMocks.getAiSettings).not.toHaveBeenCalled()
    expect(wrapper.get('#ai-save-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#ai-test-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#ai-rebuild-btn').attributes('disabled')).toBeDefined()

    await wrapper.get('#ai-save-btn').trigger('click')
    expect(aiApiMocks.updateAiSettings).not.toHaveBeenCalled()
  })
})

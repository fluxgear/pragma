<template>
  <div class='page'>
    <div class='page__header'>
      <h1>AI settings</h1>
      <p class='muted'>Configure backend-held AI providers for embeddings, editor assistance, SEO assistance, and generation smoke tests.</p>
    </div>

    <Message v-if='globalError' severity='error' :closable='false'>
      {{ globalError }}
    </Message>
    <Message v-if='actionFeedback' severity='success' :closable='false'>
      {{ actionFeedback }}
    </Message>

    <Card>
      <template #title>Provider setup</template>
      <template #content>
        <Message severity='info' :closable='false'>
          Browser UI calls only Pragma backend AI endpoints. Raw provider API tokens are accepted for update/clear operations but are never displayed after save.
        </Message>

        <Message v-if='!canManageAiSettings' severity='warn' :closable='false'>
          Only users with the AI settings permission can update provider settings or run AI administration actions.
        </Message>

        <div v-if='settingsLoading' class='muted'>Loading AI settings…</div>

        <div class='form-stack' style='margin-top: 1rem;'>
          <div class='form-grid'>
            <div class='field'>
              <label for='ai-enabled'>Provider state</label>
              <select id='ai-enabled' v-model='form.enabled' :disabled='isActionLocked'>
                <option :value='true'>Enabled</option>
                <option :value='false'>Disabled</option>
              </select>
            </div>

            <div class='field'>
              <label for='ai-provider'>Provider</label>
              <select id='ai-provider' v-model='form.provider' :disabled='isActionLocked'>
                <option v-for='option in providerOptions' :key='option.value' :value='option.value'>
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div class='field'>
              <label for='ai-display-name'>Display name</label>
              <InputText id='ai-display-name' v-model.trim='form.display_name' :disabled='isActionLocked' placeholder='Optional internal label' />
            </div>

            <div class='field'>
              <label for='ai-api-mode'>API mode</label>
              <select id='ai-api-mode' v-model='form.api_mode' :disabled='isActionLocked'>
                <option value='responses'>OpenAI Responses</option>
                <option value='chat_completions'>Chat Completions</option>
              </select>
            </div>

            <div class='field'>
              <label for='ai-auth-mode'>Auth mode</label>
              <select id='ai-auth-mode' v-model='form.auth_mode' :disabled='isActionLocked'>
                <option value='api_key'>API token</option>
                <option value='oauth'>OAuth</option>
              </select>
              <small v-if='form.auth_mode === "oauth"' class='muted'>OAuth routes are exposed through the backend, but providers are reported unsupported until OAuth metadata and token storage are configured.</small>
            </div>

            <div class='field'>
              <label for='ai-base-url'>Base URL</label>
              <InputText id='ai-base-url' v-model.trim='form.base_url' :disabled='isActionLocked' placeholder='https://api.openai.com/v1 or compatible endpoint' />
            </div>

            <div class='field'>
              <label for='ai-embedding-model'>Embedding model</label>
              <InputText id='ai-embedding-model' v-model.trim='form.embedding_model' :disabled='isActionLocked' />
            </div>

            <div class='field'>
              <label for='ai-embedding-dimensions'>Embedding dimensions</label>
              <InputText
                id='ai-embedding-dimensions'
                v-model='form.embedding_dimensions'
                type='number'
                min='1'
                max='2000'
                :disabled='isActionLocked'
              />
              <small class='muted'>Required when AI is enabled. Maximum: 2000.</small>
            </div>

            <div class='field'>
              <label for='ai-generation-model'>Generation model</label>
              <InputText id='ai-generation-model' v-model.trim='form.generation_model' :disabled='isActionLocked' placeholder='gpt-5-mini or compatible model' />
            </div>

            <div class='field'>
              <label for='ai-timeout'>Request timeout (seconds)</label>
              <InputText id='ai-timeout' v-model='form.request_timeout_seconds' type='number' min='1' max='120' :disabled='isActionLocked' />
            </div>

            <div class='field'>
              <label for='ai-api-key'>API token</label>
              <InputText
                id='ai-api-key'
                v-model.trim='form.api_key'
                :disabled='isActionLocked || form.auth_mode !== "api_key"'
                placeholder='Enter a new token; saved token is never shown'
              />
              <small class='muted'>{{ apiKeyActionDescription }}</small>
            </div>

            <div class='field field__checkbox-row'>
              <input
                id='ai-retain-api-key'
                v-model='form.retain_existing_api_key'
                type='checkbox'
                :disabled='isActionLocked || form.api_key.trim().length > 0 || form.auth_mode !== "api_key"'
              >
              <label for='ai-retain-api-key'>Keep existing API token</label>
            </div>
          </div>

          <div class='form-stack'>
            <h3>Capabilities</h3>
            <div class='form-grid'>
              <div class='field field__checkbox-row'>
                <input id='ai-cap-embeddings' type='checkbox' :checked='hasEmbeddingCapability' disabled>
                <label for='ai-cap-embeddings'>Embeddings (derived from embedding model settings)</label>
              </div>
              <div class='field field__checkbox-row'>
                <input id='ai-cap-text-generation' v-model='form.text_generation_enabled' type='checkbox' :disabled='isActionLocked'>
                <label for='ai-cap-text-generation'>Text generation</label>
              </div>
              <div class='field field__checkbox-row'>
                <input id='ai-cap-editor-assist' v-model='form.editor_assist_enabled' type='checkbox' :disabled='isActionLocked'>
                <label for='ai-cap-editor-assist'>Editor assist</label>
              </div>
              <div class='field field__checkbox-row'>
                <input id='ai-cap-seo-assist' v-model='form.seo_assist_enabled' type='checkbox' :disabled='isActionLocked'>
                <label for='ai-cap-seo-assist'>SEO assist</label>
              </div>
            </div>
            <p class='muted'>Image generation, streaming, and tool calling are visible as response capabilities when a provider supports them, but they are not enabled by this C0.3 admin surface.</p>
          </div>

          <div class='inline-actions'>
            <Button
              id='ai-save-btn'
              label='Save settings'
              icon='pi pi-save'
              :disabled='isActionLocked || settingsLoading || settings === null'
              :loading='saving'
              @click='saveSettings'
            />
            <Button
              id='ai-clear-key-btn'
              label='Clear saved token on save'
              icon='pi pi-times'
              severity='secondary'
              variant='outlined'
              :disabled='isActionLocked || settingsLoading || settings === null || !settings.api_key_status.configured'
              @click='markApiKeyForClear'
            />
            <Button
              id='ai-test-btn'
              label='Test provider'
              icon='pi pi-check-circle'
              severity='secondary'
              variant='outlined'
              :disabled='isActionLocked || settingsLoading || settings === null'
              :loading='testing'
              @click='runProviderTest'
            />
            <Button
              id='ai-rebuild-btn'
              label='Rebuild embeddings'
              icon='pi pi-sync'
              severity='secondary'
              variant='outlined'
              :disabled='isActionLocked || settingsLoading || settings === null'
              :loading='rebuilding'
              @click='runRebuild'
            />
          </div>
        </div>
      </template>
    </Card>

    <Card>
      <template #title>OAuth status</template>
      <template #content>
        <Message v-if='!canManageOauth' severity='warn' :closable='false'>
          OAuth status requires the AI OAuth permission.
        </Message>
        <Message v-else-if='oauthUnsupportedMessage' severity='warn' :closable='false'>
          {{ oauthUnsupportedMessage }}
        </Message>
        <Message v-if='oauthFeedback' severity='info' :closable='false'>
          {{ oauthFeedback }}
        </Message>

        <div class='status-list'>
          <div class='status-row'>
            <span>Supported</span>
            <Tag :severity='oauthStatus?.supported ? "success" : "warn"' :value='oauthStatus?.supported ? "Supported" : "Unsupported"' />
          </div>
          <div class='status-row'>
            <span>Connected</span>
            <Tag :severity='oauthStatus?.connected ? "success" : "warn"' :value='oauthStatus?.connected ? "Connected" : "Not connected"' />
          </div>
          <div class='status-row'>
            <span>Reason</span>
            <span class='muted code-chip'>{{ oauthStatus?.reason ?? 'Not checked' }}</span>
          </div>
        </div>

        <div class='inline-actions'>
          <Button
            id='ai-oauth-status-btn'
            label='Refresh OAuth status'
            severity='secondary'
            variant='outlined'
            :disabled='isActionLocked || !canManageOauth'
            :loading='oauthLoading'
            @click='loadOAuthStatus'
          />
          <Button
            id='ai-oauth-connect-btn'
            label='Connect with OAuth'
            severity='secondary'
            variant='outlined'
            :disabled='oauthConnectDisabled'
            :loading='oauthStarting'
            @click='startOAuthFlow'
          />
          <Button
            id='ai-oauth-disconnect-btn'
            label='Disconnect OAuth'
            severity='secondary'
            variant='outlined'
            :disabled='oauthDisconnectDisabled'
            :loading='oauthDisconnecting'
            @click='disconnectOAuth'
          />
        </div>
      </template>
    </Card>

    <Card>
      <template #title>Generation smoke test</template>
      <template #content>
        <Message severity='info' :closable='false'>
          This bounded smoke test calls Pragma backend <span class='code-chip'>/ai/generate</span> and returns draft text only. It does not insert content into an editor.
        </Message>
        <Message v-if='!canRunGenerationSmoke' severity='warn' :closable='false'>
          The selected generation scope requires {{ selectedGenerationPermission }}.
        </Message>

        <div class='form-stack' style='margin-top: 1rem;'>
          <div class='form-grid'>
            <div class='field'>
              <label for='ai-generation-scope'>Scope</label>
              <select id='ai-generation-scope' v-model='generationScope' :disabled='isActionLocked'>
                <option value='editor'>Editor assist</option>
                <option value='seo'>SEO assist</option>
              </select>
            </div>
            <div class='field'>
              <label for='ai-generation-max-tokens'>Max output tokens</label>
              <InputText id='ai-generation-max-tokens' v-model='generationMaxTokens' type='number' min='1' max='512' :disabled='isActionLocked' />
            </div>
          </div>
          <div class='field'>
            <label for='ai-generation-instructions'>Instructions</label>
            <textarea id='ai-generation-instructions' v-model.trim='generationInstructions' :disabled='isActionLocked' rows='3' />
          </div>
          <div class='field'>
            <label for='ai-generation-input'>Prompt</label>
            <textarea id='ai-generation-input' v-model.trim='generationInput' :disabled='isActionLocked' rows='4' />
          </div>
          <div class='inline-actions'>
            <Button
              id='ai-generate-btn'
              label='Run generation smoke test'
              icon='pi pi-sparkles'
              :disabled='isActionLocked || !canRunGenerationSmoke || !settings?.enabled'
              :loading='generating'
              @click='runGenerationSmoke'
            />
          </div>
          <pre v-if='generationDraft' class='code-chip'>{{ generationDraft }}</pre>
        </div>
      </template>
    </Card>

    <Card>
      <template #title>Current provider status</template>
      <template #content>
        <div class='status-list'>
          <div v-if='settings === null' class='muted'>Provider status unavailable.</div>
          <template v-else>
            <div class='status-row'>
              <span>State</span>
              <Tag :severity='settings.enabled ? "success" : "warn"' :value='settings.enabled ? "Enabled" : "Disabled"' />
            </div>
            <div class='status-row'>
              <span>Provider</span>
              <span class='code-chip'>{{ settings.provider ?? 'Not configured' }}</span>
            </div>
            <div class='status-row'>
              <span>API mode</span>
              <span class='code-chip'>{{ settings.api_mode }}</span>
            </div>
            <div class='status-row'>
              <span>Auth mode</span>
              <span class='code-chip'>{{ settings.auth_mode }}</span>
            </div>
            <div class='status-row'>
              <span>Embedding model</span>
              <span class='code-chip'>{{ settings.embedding_model ?? 'Not configured' }}</span>
            </div>
            <div class='status-row'>
              <span>Generation model</span>
              <span class='code-chip'>{{ settings.generation_model ?? 'Not configured' }}</span>
            </div>
            <div class='status-row'>
              <span>Capabilities</span>
              <span class='code-chip'>{{ settings.capabilities.length ? settings.capabilities.join(', ') : 'None' }}</span>
            </div>
            <div class='status-row'>
              <span>API token</span>
              <Tag :severity='settings.api_key_status.configured ? "info" : "warn"' :value='apiKeyStatusLabel' />
            </div>
            <div class='status-row'>
              <span>Last test</span>
              <span class='muted code-chip'>{{ settings.last_test_status ?? 'Never' }} · {{ settings.last_tested_at ?? 'not tested' }}</span>
            </div>
            <div class='status-row'>
              <span>Updated</span>
              <span class='muted code-chip'>{{ settings.updated_at ?? 'Never' }}</span>
            </div>
          </template>
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang='ts'>
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import { asUserMessage } from '@/api/errors'
import {
  disconnectAiOAuth,
  generateAiText,
  getAiOAuthStatus,
  getAiSettings,
  rebuildAiEmbeddings,
  startAiOAuth,
  testAiProvider,
  updateAiSettings,
} from '@/api/ai'
import type {
  AIGenerationResponse,
  AIGenerationScope,
  AIOAuthStatusResponse,
  AIProviderApiMode,
  AIProviderAuthMode,
  AIProviderKind,
  AIProviderSettingsResponse,
  AIProviderSettingsUpdateRequest,
  AIProviderTestResponse,
  AISearchEmbeddingRebuildResponse,
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

interface AISettingsForm {
  enabled: boolean
  provider: AIProviderKind
  display_name: string
  api_mode: AIProviderApiMode
  auth_mode: AIProviderAuthMode
  base_url: string
  embedding_model: string
  embedding_dimensions: number | string | null
  generation_model: string
  request_timeout_seconds: number | string
  api_key: string
  retain_existing_api_key: boolean
  text_generation_enabled: boolean
  editor_assist_enabled: boolean
  seo_assist_enabled: boolean
}

const authStore = useAuthStore()

const settings = ref<AIProviderSettingsResponse | null>(null)
const oauthStatus = ref<AIOAuthStatusResponse | null>(null)
const settingsLoading = ref(false)
const saving = ref(false)
const testing = ref(false)
const rebuilding = ref(false)
const generating = ref(false)
const oauthLoading = ref(false)
const oauthStarting = ref(false)
const oauthDisconnecting = ref(false)
const globalError = ref<string | null>(null)
const actionFeedback = ref<string | null>(null)
const oauthFeedback = ref<string | null>(null)
const generationDraft = ref<string | null>(null)
const generationScope = ref<AIGenerationScope>('editor')
const generationInstructions = ref('Return one short draft. Do not publish or mutate content.')
const generationInput = ref('Draft a concise section heading for a product launch page.')
const generationMaxTokens = ref<number | string>(128)

const canManageAiSettings = computed(() => authStore.hasPermission('ai.settings.manage'))
const canManageOauth = computed(() => authStore.hasPermission('ai.oauth.manage'))
const isActionLocked = computed(() => settingsLoading.value || !canManageAiSettings.value)
const selectedGenerationPermission = computed(() =>
  generationScope.value === 'seo' ? 'ai.seo_assist' : 'ai.editor_assist',
)
const canRunGenerationSmoke = computed(() => authStore.hasPermission(selectedGenerationPermission.value))

const providerOptions = [
  { label: 'Voyage AI', value: 'voyage' as AIProviderKind },
  { label: 'OpenAI', value: 'openai' as AIProviderKind },
  { label: 'OpenAI-compatible', value: 'openai_compatible' as AIProviderKind },
]

const form = reactive<AISettingsForm>({
  enabled: false,
  provider: 'openai_compatible',
  display_name: '',
  api_mode: 'chat_completions',
  auth_mode: 'api_key',
  base_url: '',
  embedding_model: '',
  embedding_dimensions: null,
  generation_model: '',
  request_timeout_seconds: 15,
  api_key: '',
  retain_existing_api_key: false,
  text_generation_enabled: false,
  editor_assist_enabled: false,
  seo_assist_enabled: false,
})

const hasEmbeddingCapability = computed(() =>
  Boolean(form.embedding_model.trim() && normalizeEmbeddingDimensionsValue(form.embedding_dimensions) !== null),
)
const apiKeyStatusLabel = computed(() => {
  const status = settings.value?.api_key_status
  if (!status?.configured) {
    return 'Missing'
  }
  return status.last4 ? `Configured · ending ${status.last4}` : 'Configured'
})
const apiKeyActionDescription = computed(() => {
  if (form.auth_mode === 'oauth') {
    return 'API token input is disabled while OAuth mode is selected.'
  }
  if (form.api_key.trim()) {
    return 'A new token will be sent to the backend and then cleared from the form.'
  }
  if (form.retain_existing_api_key && settings.value?.api_key_status.configured) {
    return `Current backend-held token will be retained${settings.value.api_key_status.last4 ? ` (ending ${settings.value.api_key_status.last4})` : ''}.`
  }
  if (!form.retain_existing_api_key && settings.value?.api_key_status.configured) {
    return 'Saved token will be cleared on the next save.'
  }
  return 'No saved token is configured.'
})
const oauthUnsupportedMessage = computed(() =>
  oauthStatus.value && !oauthStatus.value.supported ? oauthStatus.value.reason : null,
)
const oauthConnectDisabled = computed(() =>
  isActionLocked.value || !canManageOauth.value || oauthStarting.value || oauthStatus.value?.supported === false,
)
const oauthDisconnectDisabled = computed(() =>
  isActionLocked.value ||
  !canManageOauth.value ||
  oauthDisconnecting.value ||
  !oauthStatus.value?.connected,
)

function applySettings(payload: AIProviderSettingsResponse): void {
  settings.value = payload
  form.enabled = payload.enabled
  form.provider = payload.provider ?? 'openai_compatible'
  form.display_name = payload.display_name ?? ''
  form.api_mode = payload.api_mode
  form.auth_mode = payload.auth_mode
  form.base_url = payload.base_url ?? ''
  form.embedding_model = payload.embedding_model ?? ''
  form.embedding_dimensions = payload.embedding_dimensions
  form.generation_model = payload.generation_model ?? ''
  form.request_timeout_seconds = payload.request_timeout_seconds ?? 15
  form.api_key = ''
  form.retain_existing_api_key = payload.api_key_status.configured
  form.text_generation_enabled = payload.capabilities.includes('text_generation')
  form.editor_assist_enabled = payload.capabilities.includes('editor_assist')
  form.seo_assist_enabled = payload.capabilities.includes('seo_assist')
}

function clearActionFeedback(): void {
  actionFeedback.value = null
  globalError.value = null
}

function setActionMessage(message: string): void {
  actionFeedback.value = message
}

function normalizeOptionalText(value: string): string | null {
  const normalized = value.trim()
  return normalized || null
}

function normalizeTimeout(): number {
  const timeout = Number(form.request_timeout_seconds)
  if (!Number.isFinite(timeout) || timeout < 1) {
    return 15
  }

  return Math.min(Math.trunc(timeout), 120)
}

function normalizeEmbeddingDimensionsValue(value: number | string | null): number | null {
  if (value === null || value === '') {
    return null
  }

  const dimensions = Number(value)
  if (!Number.isFinite(dimensions) || dimensions < 1 || dimensions > 2000) {
    return null
  }

  return Math.trunc(dimensions)
}

function normalizeEmbeddingDimensions(): number | null {
  const dimensions = normalizeEmbeddingDimensionsValue(form.embedding_dimensions)
  if (form.enabled && dimensions === null) {
    throw new Error('Embedding dimensions are required when AI is enabled and must be between 1 and 2000.')
  }
  return dimensions
}

function normalizeGenerationMaxTokens(): number {
  const maxTokens = Number(generationMaxTokens.value)
  if (!Number.isFinite(maxTokens) || maxTokens < 1) {
    return 128
  }
  return Math.min(Math.trunc(maxTokens), 512)
}

async function loadSettings(): Promise<void> {
  settingsLoading.value = true
  clearActionFeedback()
  try {
    const response = await getAiSettings()
    applySettings(response)
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    settingsLoading.value = false
  }
}

async function loadOAuthStatus(): Promise<void> {
  if (!canManageOauth.value) {
    return
  }

  oauthLoading.value = true
  oauthFeedback.value = null
  try {
    oauthStatus.value = await getAiOAuthStatus()
  } catch (error) {
    oauthFeedback.value = `OAuth status unavailable: ${asUserMessage(error)}`
  } finally {
    oauthLoading.value = false
  }
}

function markApiKeyForClear(): void {
  form.api_key = ''
  form.retain_existing_api_key = false
}

async function saveSettings(): Promise<void> {
  clearActionFeedback()
  if (!canManageAiSettings.value) {
    return
  }

  saving.value = true

  try {
    if (form.auth_mode === 'oauth' && form.enabled) {
      throw new Error('OAuth auth mode is unavailable for enabled provider calls in this release. Use API token mode.')
    }

    const hasPersistedKey = settings.value?.api_key_status.configured ?? false
    const rawApiKey = form.api_key.trim()

    if (
      form.enabled &&
      form.auth_mode === 'api_key' &&
      !rawApiKey &&
      !form.retain_existing_api_key &&
      !hasPersistedKey
    ) {
      throw new Error('An API token is required when AI is enabled.')
    }

    const normalizedBaseUrl = normalizeOptionalText(form.base_url)
    const normalizedDisplayName = normalizeOptionalText(form.display_name)
    const normalizedEmbeddingModel = normalizeOptionalText(form.embedding_model)
    const normalizedEmbeddingDimensions = normalizeEmbeddingDimensions()
    const normalizedGenerationModel = normalizeOptionalText(form.generation_model)
    const generationRequested =
      form.text_generation_enabled || form.editor_assist_enabled || form.seo_assist_enabled

    if (generationRequested && normalizedGenerationModel === null) {
      throw new Error('A generation model is required when generation capabilities are enabled.')
    }

    const shouldPersistProvider = Boolean(
      form.enabled ||
        normalizedBaseUrl ||
        normalizedDisplayName ||
        normalizedEmbeddingModel ||
        normalizedGenerationModel ||
        generationRequested,
    )

    const payload: AIProviderSettingsUpdateRequest = {
      enabled: form.enabled,
      provider: shouldPersistProvider ? form.provider : null,
      display_name: normalizedDisplayName,
      api_mode: form.api_mode,
      auth_mode: form.auth_mode,
      base_url: normalizedBaseUrl,
      embedding_model: normalizedEmbeddingModel,
      embedding_dimensions: normalizedEmbeddingDimensions,
      generation_model: normalizedGenerationModel,
      text_generation_enabled: form.text_generation_enabled,
      editor_assist_enabled: form.editor_assist_enabled,
      seo_assist_enabled: form.seo_assist_enabled,
      request_timeout_seconds: normalizeTimeout(),
      retain_existing_api_key: form.retain_existing_api_key,
    }

    if (rawApiKey) {
      payload.api_key = rawApiKey
    } else if (!form.retain_existing_api_key) {
      payload.api_key = null
    }

    const response = await updateAiSettings(payload)
    applySettings(response)

    let message = 'AI settings saved successfully.'
    if (response.embeddings_rebuild_required) {
      try {
        const rebuildResponse: AISearchEmbeddingRebuildResponse = await rebuildAiEmbeddings({
          batch_size: 20,
          max_documents: 200,
          force: true,
        })
        message += ` Rebuild started: ${rebuildResponse.embedded}/${rebuildResponse.attempted} embedded, ${rebuildResponse.failed} failed`
      } catch (error) {
        globalError.value = `AI settings saved, but embedding rebuild could not be started: ${asUserMessage(error)}`
        return
      }
    }
    setActionMessage(message)
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    saving.value = false
  }
}

async function runProviderTest(): Promise<void> {
  clearActionFeedback()
  if (!canManageAiSettings.value) {
    return
  }

  testing.value = true
  try {
    const response: AIProviderTestResponse = await testAiProvider()
    setActionMessage(
      `Provider test passed: ${response.provider} (${response.embedding_model}, ${response.embedding_dimensions} dimensions)`,
    )
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    testing.value = false
  }
}

async function runGenerationSmoke(): Promise<void> {
  clearActionFeedback()
  generationDraft.value = null
  if (!canRunGenerationSmoke.value) {
    return
  }

  const input = generationInput.value.trim()
  if (!input) {
    globalError.value = 'Enter a prompt before running the generation smoke test.'
    return
  }

  generating.value = true
  try {
    const response: AIGenerationResponse = await generateAiText({
      scope: generationScope.value,
      input,
      instructions: normalizeOptionalText(generationInstructions.value),
      model: normalizeOptionalText(form.generation_model),
      max_output_tokens: normalizeGenerationMaxTokens(),
    })
    generationDraft.value = response.text
    setActionMessage(`Generation smoke test completed through ${response.provider} ${response.api_mode}.`)
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    generating.value = false
  }
}

async function startOAuthFlow(): Promise<void> {
  if (!canManageOauth.value) {
    return
  }

  oauthStarting.value = true
  oauthFeedback.value = null
  try {
    const response = await startAiOAuth()
    oauthFeedback.value = response.supported
      ? 'OAuth start returned an authorization URL. Browser redirect is intentionally not automatic from this admin smoke UI.'
      : response.reason
    await loadOAuthStatus()
  } catch (error) {
    oauthFeedback.value = asUserMessage(error)
  } finally {
    oauthStarting.value = false
  }
}

async function disconnectOAuth(): Promise<void> {
  if (!canManageOauth.value) {
    return
  }

  oauthDisconnecting.value = true
  oauthFeedback.value = null
  try {
    oauthStatus.value = await disconnectAiOAuth()
    oauthFeedback.value = oauthStatus.value.reason
  } catch (error) {
    oauthFeedback.value = asUserMessage(error)
  } finally {
    oauthDisconnecting.value = false
  }
}

async function runRebuild(): Promise<void> {
  clearActionFeedback()
  if (!canManageAiSettings.value) {
    return
  }

  rebuilding.value = true
  try {
    const response: AISearchEmbeddingRebuildResponse = await rebuildAiEmbeddings({
      batch_size: 20,
      max_documents: 200,
      force: false,
    })
    setActionMessage(
      `Rebuild batch complete: ${response.embedded}/${response.attempted} embedded, ${response.failed} failed`,
    )
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    rebuilding.value = false
  }
}

onMounted(async () => {
  if (!canManageAiSettings.value) {
    return
  }

  await loadSettings()
  await loadOAuthStatus()
})
</script>

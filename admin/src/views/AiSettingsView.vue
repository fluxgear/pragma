<template>
  <div class="page">
    <div class="page__header">
      <h1>AI settings</h1>
      <p class="muted">Optional AI provider settings for semantic vector features.</p>
    </div>

    <Message v-if="globalError" severity="error" :closable="false">
      {{ globalError }}
    </Message>
    <Message v-if="actionFeedback" severity="success" :closable="false">
      {{ actionFeedback }}
    </Message>

    <Card>
      <template #title>Provider setup</template>
      <template #content>
        <Message severity="info" :closable="false">
          AI is optional. Leave it disabled if you want core content workflows to run without vector-provider dependencies.
        </Message>

        <Message v-if="!isSuperuser" severity="warn" :closable="false">
          Only super-admin users can update provider settings or run rebuild actions.
        </Message>

        <div v-if="settingsLoading" class="muted">Loading AI settings…</div>

        <div class="form-stack" style="margin-top: 1rem;">
          <div class="form-grid">
            <div class="field">
              <label for="ai-enabled">Provider state</label>
              <Select
                id="ai-enabled"
                v-model="form.enabled"
                :options="enabledOptions"
                optionLabel="label"
                optionValue="value"
                :disabled="isActionLocked"
              />
            </div>

            <div class="field">
              <label for="ai-provider">Provider</label>
              <Select
                id="ai-provider"
                v-model="form.provider"
                :options="providerOptions"
                optionLabel="label"
                optionValue="value"
                :disabled="isActionLocked"
              />
            </div>

            <div class="field">
              <label for="ai-base-url">Base URL</label>
              <InputText id="ai-base-url" v-model.trim="form.base_url" :disabled="isActionLocked" />
            </div>

            <div class="field">
              <label for="ai-embedding-model">Embedding model</label>
              <InputText id="ai-embedding-model" v-model.trim="form.embedding_model" :disabled="isActionLocked" />
            </div>

            <div class="field">
              <label for="ai-timeout">Request timeout (seconds)</label>
              <InputText id="ai-timeout" v-model="form.request_timeout_seconds" type="number" :disabled="isActionLocked" />
            </div>

            <div class="field">
              <label for="ai-api-key">API key</label>
              <InputText
                id="ai-api-key"
                v-model.trim="form.api_key"
                :disabled="isActionLocked"
                placeholder="Leave empty to keep current key"
              />
            </div>

            <div class="field field__checkbox-row">
              <Checkbox
                id="ai-retain-api-key"
                v-model="form.retain_existing_api_key"
                :binary="true"
                :disabled="isActionLocked"
              />
              <label for="ai-retain-api-key">Keep existing API key</label>
            </div>
          </div>

          <div class="inline-actions">
            <Button
              id="ai-save-btn"
              label="Save settings"
              icon="pi pi-save"
              :disabled="isActionLocked || settingsLoading || settings === null"
              :loading="saving"
              @click="saveSettings"
            />
            <Button
              id="ai-test-btn"
              label="Test provider"
              icon="pi pi-check-circle"
              severity="secondary"
              variant="outlined"
              :disabled="isActionLocked || settingsLoading || settings === null"
              :loading="testing"
              @click="runProviderTest"
            />
            <Button
              id="ai-rebuild-btn"
              label="Rebuild embeddings"
              icon="pi pi-sync"
              severity="secondary"
              variant="outlined"
              :disabled="isActionLocked || settingsLoading || settings === null"
              :loading="rebuilding"
              @click="runRebuild"
            />
          </div>
        </div>
      </template>
    </Card>

    <Card>
      <template #title>Current provider status</template>
      <template #content>
        <div class="status-list">
          <div v-if="settings === null" class="muted">Provider status unavailable.</div>
          <template v-else>
            <div class="status-row">
              <span>State</span>
              <Tag :severity="settings.enabled ? 'success' : 'warn'" :value="settings.enabled ? 'Enabled' : 'Disabled'" />
            </div>
            <div class="status-row">
              <span>Provider</span>
              <span class="code-chip">{{ settings.provider ?? 'Not configured' }}</span>
            </div>
            <div class="status-row">
              <span>API key</span>
              <Tag :severity="settings.api_key_configured ? 'info' : 'warn'" :value="settings.api_key_configured ? 'Configured' : 'Missing'" />
            </div>
            <div class="status-row">
              <span>Updated</span>
              <span class="muted code-chip">{{ settings.updated_at ?? 'Never' }}</span>
            </div>
          </template>
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { storeToRefs } from 'pinia'

import { asUserMessage } from '@/api/errors'
import { getAiSettings, rebuildAiEmbeddings, testAiProvider, updateAiSettings } from '@/api/ai'
import type {
  AIProviderKind,
  AIProviderSettingsResponse,
  AIProviderSettingsUpdateRequest,
  AIProviderTestResponse,
  AISearchEmbeddingRebuildResponse,
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const settings = ref<AIProviderSettingsResponse | null>(null)
const settingsLoading = ref(false)
const saving = ref(false)
const testing = ref(false)
const rebuilding = ref(false)
const globalError = ref<string | null>(null)
const actionFeedback = ref<string | null>(null)

const isSuperuser = computed(() => user.value?.is_superuser === true)
const isActionLocked = computed(() => settingsLoading.value || !isSuperuser.value)

const enabledOptions = [
  { label: 'Enabled', value: true },
  { label: 'Disabled', value: false },
]

const providerOptions = [
  { label: 'Voyage AI', value: 'voyage' as AIProviderKind },
  { label: 'OpenAI-compatible', value: 'openai_compatible' as AIProviderKind },
]

const form = reactive({
  enabled: false,
  provider: 'voyage' as AIProviderKind,
  base_url: '',
  embedding_model: '',
  request_timeout_seconds: 15,
  api_key: '',
  retain_existing_api_key: true,
})

function applySettings(payload: AIProviderSettingsResponse): void {
  settings.value = payload
  form.enabled = payload.enabled
  form.provider = payload.provider ?? 'voyage'
  form.base_url = payload.base_url ?? ''
  form.embedding_model = payload.embedding_model ?? ''
  form.request_timeout_seconds = payload.request_timeout_seconds ?? 15
  form.api_key = ''
  form.retain_existing_api_key = payload.api_key_configured
}

function clearActionFeedback(): void {
  actionFeedback.value = null
  globalError.value = null
}

function setActionMessage(message: string): void {
  actionFeedback.value = message
}

function normalizeTimeout(): number {
  const timeout = Number(form.request_timeout_seconds)
  if (!Number.isFinite(timeout) || timeout < 1) {
    return 15
  }

  return Math.trunc(timeout)
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

async function saveSettings(): Promise<void> {
  clearActionFeedback()
  if (!isSuperuser.value) {
    return
  }

  saving.value = true

  try {
    const hasPersistedKey = settings.value?.api_key_configured ?? false
    const rawApiKey = form.api_key.trim()

    if (
      form.enabled &&
      !rawApiKey &&
      !form.retain_existing_api_key &&
      !hasPersistedKey
    ) {
      throw new Error('An API key is required when AI is enabled.')
    }

    const normalizedBaseUrl = form.base_url.trim()
    const normalizedEmbeddingModel = form.embedding_model.trim()

    const payload: AIProviderSettingsUpdateRequest = {
      enabled: form.enabled,
      provider:
        form.enabled || normalizedBaseUrl || normalizedEmbeddingModel ? form.provider : null,
      base_url: normalizedBaseUrl || null,
      embedding_model: normalizedEmbeddingModel || null,
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
    setActionMessage('AI settings saved successfully.')
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    saving.value = false
  }
}

async function runProviderTest(): Promise<void> {
  clearActionFeedback()
  if (!isSuperuser.value) {
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

async function runRebuild(): Promise<void> {
  clearActionFeedback()
  if (!isSuperuser.value) {
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
      `Rebuild complete: ${response.embedded}/${response.attempted} embedded, ${response.failed} failed`,
    )
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    rebuilding.value = false
  }
}

onMounted(async () => {
  if (!isSuperuser.value) {
    return
  }

  await loadSettings()
})
</script>

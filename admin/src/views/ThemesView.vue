<template>
  <div class="page themes-view">
    <div class="page__header themes-view__header">
      <div>
        <h1>Themes</h1>
        <p class="muted">Discover installed themes, activate the public theme, and edit safe design tokens.</p>
      </div>
      <div class="inline-actions">
        <Button
          id="themes-refresh-btn"
          label="Refresh"
          icon="pi pi-refresh"
          severity="secondary"
          variant="outlined"
          :loading="loading"
          :disabled="!canManageThemes"
          @click="loadThemes"
        />
      </div>
    </div>

    <Message v-if="!canManageThemes" severity="warn" :closable="false">
      Theme administration requires themes.manage.
    </Message>
    <Message v-if="globalError" severity="error" :closable="false">
      {{ globalError }}
    </Message>
    <Message v-if="actionFeedback" severity="success" closable @close="actionFeedback = null">
      {{ actionFeedback }}
    </Message>

    <div v-if="loading && settings === null" class="loading-state">Loading discovered themes…</div>

    <template v-else>
      <Card>
        <template #title>Current theme state</template>
        <template #content>
          <div v-if="settings === null" class="empty-state">
            Theme settings are unavailable until the backend responds.
          </div>
          <div v-else class="status-list">
            <div class="status-row">
              <span>Active theme</span>
              <span class="code-chip">{{ settings.active_theme_id }}</span>
            </div>
            <div class="status-row">
              <span>Current runtime theme</span>
              <span class="code-chip">{{ settings.current_theme_id ?? 'Fallback pending' }}</span>
            </div>
            <div class="status-row">
              <span>Default theme</span>
              <span class="code-chip">{{ settings.default_theme_id }}</span>
            </div>
            <div class="status-row">
              <span>Persisted override</span>
              <span class="code-chip">{{ settings.persisted_active_theme_id ?? 'None · environment/default behavior' }}</span>
            </div>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Discovered themes</template>
        <template #content>
          <Message severity="info" :closable="false">
            No live theme preview is implemented in this admin surface. Selecting a theme only inspects its metadata; use Activate selected theme to change the public site.
          </Message>

          <div v-if="themes.length === 0" class="empty-state" data-testid="themes-empty-state">
            No themes have been discovered by the backend runtime.
          </div>

          <div v-else class="themes-view__grid" role="list" aria-label="Discovered themes">
            <button
              v-for="theme in themes"
              :key="theme.id"
              type="button"
              class="themes-view__theme-card"
              :class="{ 'themes-view__theme-card--selected': selectedThemeId === theme.id }"
              :aria-pressed="selectedThemeId === theme.id ? 'true' : 'false'"
              :data-testid="`theme-card-${theme.id}`"
              @click="selectTheme(theme.id)"
            >
              <span class="themes-view__theme-title">{{ theme.name }}</span>
              <span class="muted">{{ theme.id }} · v{{ theme.version }}</span>
              <span v-if="theme.description" class="muted">{{ theme.description }}</span>
              <span class="themes-view__badges">
                <Tag v-if="theme.active" severity="success" value="Active" />
                <Tag v-if="theme.current" severity="info" value="Current" />
                <Tag v-if="theme.default" severity="secondary" value="Default" />
                <Tag :severity="theme.available ? 'success' : 'danger'" :value="theme.available ? 'Available' : 'Unavailable'" />
              </span>
            </button>
          </div>

          <div class="themes-view__selected-panel">
            <div>
              <h3>Selected theme</h3>
              <p class="muted">{{ selectedThemeSummary }}</p>
            </div>
            <div class="inline-actions">
              <Button
                id="themes-activate-btn"
                label="Activate selected theme"
                icon="pi pi-check-circle"
                :disabled="activateDisabled"
                :loading="activating"
                @click="activateSelectedTheme"
              />
              <Button
                id="themes-reset-btn"
                label="Reset to environment default"
                icon="pi pi-undo"
                severity="secondary"
                variant="outlined"
                :disabled="actionLocked || settings === null"
                :loading="resetting"
                @click="resetToDefault"
              />
            </div>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Safe design settings</template>
        <template #content>
          <Message v-if="settings?.design_warnings.length" severity="warn" :closable="false">
            <ul class="themes-view__warning-list">
              <li v-for="warning in settings.design_warnings" :key="warning">{{ warning }}</li>
            </ul>
          </Message>

          <div v-if="settings === null" class="empty-state">Load theme settings before editing design tokens.</div>
          <div v-else class="form-stack">
            <div class="themes-view__swatches" aria-label="Current design color tokens">
              <span :style="swatchStyle(designForm.primary_color)">Primary</span>
              <span :style="swatchStyle(designForm.accent_color)">Accent</span>
              <span :style="swatchStyle(designForm.background_color)">Background</span>
              <span :style="swatchStyle(designForm.text_color)">Text</span>
            </div>

            <div class="form-grid">
              <div class="field">
                <label for="theme-primary-color">Primary color</label>
                <InputText id="theme-primary-color" v-model.trim="designForm.primary_color" pattern="#[0-9a-fA-F]{6}" :disabled="actionLocked" />
              </div>
              <div class="field">
                <label for="theme-accent-color">Accent color</label>
                <InputText id="theme-accent-color" v-model.trim="designForm.accent_color" pattern="#[0-9a-fA-F]{6}" :disabled="actionLocked" />
              </div>
              <div class="field">
                <label for="theme-background-color">Background color</label>
                <InputText id="theme-background-color" v-model.trim="designForm.background_color" pattern="#[0-9a-fA-F]{6}" :disabled="actionLocked" />
              </div>
              <div class="field">
                <label for="theme-text-color">Text color</label>
                <InputText id="theme-text-color" v-model.trim="designForm.text_color" pattern="#[0-9a-fA-F]{6}" :disabled="actionLocked" />
              </div>
              <div class="field">
                <label for="theme-typography-preset">Typography preset</label>
                <select id="theme-typography-preset" v-model="designForm.typography_preset" :disabled="actionLocked">
                  <option value="system">System</option>
                  <option value="serif">Serif</option>
                  <option value="editorial">Editorial</option>
                </select>
              </div>
              <div class="field">
                <label for="theme-spacing-scale">Spacing scale</label>
                <select id="theme-spacing-scale" v-model="designForm.spacing_scale" :disabled="actionLocked">
                  <option value="compact">Compact</option>
                  <option value="comfortable">Comfortable</option>
                  <option value="spacious">Spacious</option>
                </select>
              </div>
              <div class="field">
                <label for="theme-radius-scale">Radius scale</label>
                <select id="theme-radius-scale" v-model="designForm.radius_scale" :disabled="actionLocked">
                  <option value="none">None</option>
                  <option value="small">Small</option>
                  <option value="medium">Medium</option>
                  <option value="large">Large</option>
                </select>
              </div>
            </div>

            <div class="inline-actions">
              <Button
                id="themes-save-design-btn"
                label="Save design settings"
                icon="pi pi-save"
                :disabled="actionLocked || settings === null"
                :loading="savingDesign"
                @click="saveDesignSettings"
              />
            </div>
          </div>
        </template>
      </Card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import { asUserMessage } from '@/api/errors'
import { listThemes, resetThemeSettings, updateThemeSettings } from '@/api/themes'
import type {
  ThemeDesignSettings,
  ThemeManifestResponse,
  ThemeRadiusScale,
  ThemeSettingsResponse,
  ThemeSpacingScale,
  ThemeTypographyPreset,
} from '@/api/types'
import { useAuthStore } from '@/stores/auth'

interface ThemeDesignForm {
  primary_color: string
  accent_color: string
  background_color: string
  text_color: string
  typography_preset: ThemeTypographyPreset
  spacing_scale: ThemeSpacingScale
  radius_scale: ThemeRadiusScale
}

const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/
const authStore = useAuthStore()

const settings = ref<ThemeSettingsResponse | null>(null)
const selectedThemeId = ref<string | null>(null)
const loading = ref(false)
const activating = ref(false)
const resetting = ref(false)
const savingDesign = ref(false)
const globalError = ref<string | null>(null)
const actionFeedback = ref<string | null>(null)

const designForm = reactive<ThemeDesignForm>({
  primary_color: '#2563eb',
  accent_color: '#7c3aed',
  background_color: '#ffffff',
  text_color: '#111827',
  typography_preset: 'system',
  spacing_scale: 'comfortable',
  radius_scale: 'medium',
})

const canManageThemes = computed(() => authStore.hasPermission('themes.manage'))
const themes = computed(() => settings.value?.themes ?? [])
const selectedTheme = computed<ThemeManifestResponse | null>(() => {
  if (selectedThemeId.value === null) {
    return null
  }
  return themes.value.find((theme) => theme.id === selectedThemeId.value) ?? null
})
const actionLocked = computed(() => loading.value || !canManageThemes.value)
const activateDisabled = computed(
  () =>
    actionLocked.value ||
    settings.value === null ||
    selectedTheme.value === null ||
    selectedThemeId.value === settings.value.active_theme_id ||
    !selectedTheme.value.available,
)
const selectedThemeSummary = computed(() => {
  if (selectedTheme.value === null) {
    return themes.value.length ? 'Select a discovered theme to inspect metadata before activation.' : 'No discovered theme is selected.'
  }

  const author = selectedTheme.value.author ? ` by ${selectedTheme.value.author}` : ''
  const activation = selectedTheme.value.active ? 'This theme is already active.' : 'Activation will update the public runtime after backend validation.'
  return `${selectedTheme.value.name} ${selectedTheme.value.version}${author}. ${activation}`
})

function applySettings(payload: ThemeSettingsResponse): void {
  settings.value = payload
  selectedThemeId.value = payload.themes.find((theme) => theme.id === selectedThemeId.value)?.id
    ?? payload.active_theme_id
    ?? payload.current_theme_id
    ?? payload.themes[0]?.id
    ?? null
  applyDesignSettings(payload.design_settings)
}

function applyDesignSettings(payload: ThemeDesignSettings): void {
  designForm.primary_color = payload.primary_color
  designForm.accent_color = payload.accent_color
  designForm.background_color = payload.background_color
  designForm.text_color = payload.text_color
  designForm.typography_preset = payload.typography_preset
  designForm.spacing_scale = payload.spacing_scale
  designForm.radius_scale = payload.radius_scale
}

function clearMessages(): void {
  globalError.value = null
  actionFeedback.value = null
}

async function loadThemes(): Promise<void> {
  if (!canManageThemes.value) {
    return
  }

  loading.value = true
  clearMessages()
  try {
    applySettings(await listThemes())
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    loading.value = false
  }
}

function selectTheme(themeId: string): void {
  selectedThemeId.value = themeId
}

function normalizeHexColor(value: string, label: string): string {
  const normalized = value.trim().toLowerCase()
  if (!HEX_COLOR_PATTERN.test(normalized)) {
    throw new Error(`${label} must be a six-digit hex color, for example #2563eb.`)
  }
  return normalized
}

function buildDesignPayload(): ThemeDesignSettings {
  return {
    primary_color: normalizeHexColor(designForm.primary_color, 'Primary color'),
    accent_color: normalizeHexColor(designForm.accent_color, 'Accent color'),
    background_color: normalizeHexColor(designForm.background_color, 'Background color'),
    text_color: normalizeHexColor(designForm.text_color, 'Text color'),
    typography_preset: designForm.typography_preset,
    spacing_scale: designForm.spacing_scale,
    radius_scale: designForm.radius_scale,
  }
}

async function activateSelectedTheme(): Promise<void> {
  if (selectedThemeId.value === null || settings.value === null || !canManageThemes.value) {
    return
  }

  activating.value = true
  clearMessages()
  try {
    const response = await updateThemeSettings({ active_theme_id: selectedThemeId.value })
    applySettings(response)
    actionFeedback.value = `${selectedTheme.value?.name ?? selectedThemeId.value} activated. Public rendering now follows the backend active-theme setting.`
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    activating.value = false
  }
}

async function resetToDefault(): Promise<void> {
  if (!canManageThemes.value) {
    return
  }

  resetting.value = true
  clearMessages()
  try {
    const response = await resetThemeSettings()
    applySettings(response)
    actionFeedback.value = 'Theme settings reset to environment/default behavior.'
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    resetting.value = false
  }
}

async function saveDesignSettings(): Promise<void> {
  if (!canManageThemes.value) {
    return
  }

  savingDesign.value = true
  clearMessages()
  try {
    const response = await updateThemeSettings({ design_settings: buildDesignPayload() })
    applySettings(response)
    actionFeedback.value = 'Design settings saved.'
  } catch (error) {
    globalError.value = asUserMessage(error)
  } finally {
    savingDesign.value = false
  }
}

function swatchStyle(color: string): Record<string, string> {
  return {
    backgroundColor: color,
    color: color.toLowerCase() === '#ffffff' ? '#111827' : '#ffffff',
  }
}

onMounted(async () => {
  await loadThemes()
})
</script>

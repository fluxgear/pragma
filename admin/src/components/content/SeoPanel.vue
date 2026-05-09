<template>
  <section class="content-seo-panel form-stack" aria-labelledby="content-seo-panel-title">
    <div class="content-seo-panel__header">
      <div>
        <p class="muted">SEO and social metadata</p>
        <h3 id="content-seo-panel-title">Search preview fields</h3>
        <p class="muted">
          These fields save with the draft entry. Publishing remains a separate manual workflow action.
        </p>
      </div>
      <Tag value="Draft metadata" severity="info" />
    </div>

    <div class="form-grid">
      <div class="field">
        <label for="entry-seo-title">SEO title</label>
        <InputText
          id="entry-seo-title"
          :model-value="modelValue.title"
          :disabled="readOnly"
          maxlength="160"
          data-testid="seo-title"
          @update:model-value="updateField('title', String($event ?? ''))"
        />
      </div>

      <div class="field">
        <label for="entry-seo-canonical">Canonical URL override</label>
        <InputText
          id="entry-seo-canonical"
          :model-value="modelValue.canonical_url"
          :disabled="readOnly"
          placeholder="/page-path or https://example.test/page"
          data-testid="seo-canonical-url"
          @update:model-value="updateField('canonical_url', String($event ?? ''))"
        />
      </div>

      <div class="field field--full">
        <label for="entry-seo-description">Meta description</label>
        <Textarea
          id="entry-seo-description"
          :model-value="modelValue.description"
          :disabled="readOnly"
          rows="3"
          maxlength="320"
          data-testid="seo-description"
          @update:model-value="updateField('description', String($event ?? ''))"
        />
      </div>

      <div class="field">
        <label for="entry-seo-robots">Robots</label>
        <Select
          id="entry-seo-robots"
          :model-value="modelValue.robots"
          :options="robotsOptions"
          optionLabel="label"
          optionValue="value"
          :disabled="readOnly"
          data-testid="seo-robots"
          @update:model-value="updateField('robots', $event === 'noindex' ? 'noindex' : 'index')"
        />
        <small class="muted">Preview URLs are always noindex/nofollow on the public route.</small>
      </div>

      <div class="field">
        <label for="entry-seo-og-image">Social image URL</label>
        <InputText
          id="entry-seo-og-image"
          :model-value="modelValue.og_image"
          :disabled="readOnly"
          placeholder="/media/hero.jpg or https://cdn.example.test/hero.jpg"
          data-testid="seo-og-image"
          @update:model-value="updateField('og_image', String($event ?? ''))"
        />
      </div>

      <div class="field">
        <label for="entry-seo-og-title">Social title</label>
        <InputText
          id="entry-seo-og-title"
          :model-value="modelValue.og_title"
          :disabled="readOnly"
          maxlength="160"
          data-testid="seo-og-title"
          @update:model-value="updateField('og_title', String($event ?? ''))"
        />
      </div>

      <div class="field">
        <label for="entry-seo-og-description">Social description</label>
        <Textarea
          id="entry-seo-og-description"
          :model-value="modelValue.og_description"
          :disabled="readOnly"
          rows="3"
          maxlength="320"
          data-testid="seo-og-description"
          @update:model-value="updateField('og_description', String($event ?? ''))"
        />
      </div>
    </div>

    <section class="content-seo-panel__ai form-stack" aria-labelledby="content-seo-ai-title" data-testid="seo-ai-panel">
      <div class="content-seo-panel__ai-header">
        <div>
          <p class="muted">AI SEO assist</p>
          <h4 id="content-seo-ai-title">Generate draft suggestions</h4>
          <p class="muted">
            Uses the backend /ai/generate SEO scope only. Suggestions stay local until you accept them into the fields above.
          </p>
        </div>
        <Button
          type="button"
          label="Generate SEO suggestions"
          icon="pi pi-sparkles"
          data-testid="seo-ai-generate"
          :disabled="readOnly || generating"
          :loading="generating"
          @click="generateSuggestion"
        />
      </div>

      <Message v-if="readOnly" severity="warn" :closable="false" data-testid="seo-ai-read-only">
        AI SEO suggestions are unavailable in read-only mode. AI cannot save, schedule, or publish entries.
      </Message>
      <Message v-if="aiErrorMessage" severity="error" :closable="false" data-testid="seo-ai-error">
        {{ aiErrorMessage }}
      </Message>

      <article v-if="suggestion" class="content-seo-panel__suggestion" data-testid="seo-ai-suggestion">
        <div>
          <strong>Draft suggestion</strong>
          <p class="muted">Review before accepting. Accepting only fills the editable SEO fields; it does not save or publish.</p>
        </div>
        <dl class="content-seo-panel__suggestion-list">
          <template v-for="item in suggestionItems" :key="item.key">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </template>
        </dl>
        <div class="inline-actions">
          <Button type="button" label="Accept into SEO fields" icon="pi pi-check" data-testid="seo-ai-accept" :disabled="readOnly" @click="acceptSuggestion" />
          <Button type="button" label="Dismiss" severity="secondary" variant="outlined" data-testid="seo-ai-dismiss" @click="dismissSuggestion" />
        </div>
      </article>
      <p v-else class="muted" data-testid="seo-ai-empty">Generated SEO and social suggestions appear here for review.</p>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import { generateAiText } from '@/api/ai'
import { ApiClientError, asUserMessage } from '@/api/errors'
import type { ContentEntryResponse, ContentSeoRobots, ContentTypeResponse } from '@/api/types'
import type { ContentEntrySeoMetadataFormState } from '@/features/content/form'

interface SeoSuggestion {
  title?: string
  description?: string
  og_title?: string
  og_description?: string
}

const props = withDefaults(defineProps<{
  modelValue: ContentEntrySeoMetadataFormState
  contentType: ContentTypeResponse
  entry?: ContentEntryResponse | null
  payload?: Record<string, unknown>
  readOnly?: boolean
}>(), {
  entry: null,
  payload: () => ({}),
  readOnly: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: ContentEntrySeoMetadataFormState]
}>()

const robotsOptions: Array<{ label: string; value: ContentSeoRobots }> = [
  { label: 'Index', value: 'index' },
  { label: 'Noindex', value: 'noindex' },
]

const generating = ref(false)
const aiErrorMessage = ref<string | null>(null)
const suggestion = ref<SeoSuggestion | null>(null)

const suggestionItems = computed(() => {
  const current = suggestion.value ?? {}
  return [
    { key: 'title', label: 'SEO title', value: current.title },
    { key: 'description', label: 'Meta description', value: current.description },
    { key: 'og_title', label: 'Social title', value: current.og_title },
    { key: 'og_description', label: 'Social description', value: current.og_description },
  ].filter((item): item is { key: string; label: string; value: string } => typeof item.value === 'string' && item.value.trim().length > 0)
})

function updateField<K extends keyof ContentEntrySeoMetadataFormState>(
  key: K,
  value: ContentEntrySeoMetadataFormState[K],
): void {
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: value,
  })
}

function clippedJson(value: unknown): string {
  const serialized = JSON.stringify(value, null, 2) ?? ''
  return serialized.length > 2400 ? `${serialized.slice(0, 2400)}…` : serialized
}

function buildAiInput(): string {
  return [
    `Content type: ${props.contentType.name} (${props.contentType.slug})`,
    `Entry slug: ${props.entry?.slug ?? props.modelValue.title ?? 'new-draft'}`,
    `Entry status: ${props.entry?.status ?? 'draft'}`,
    `Current SEO metadata: ${clippedJson(props.modelValue)}`,
    `Draft content fields: ${clippedJson(props.payload)}`,
  ].join('\n')
}

function stripCodeFence(text: string): string {
  const trimmed = text.trim()
  if (!trimmed.startsWith('```')) {
    return trimmed
  }

  return trimmed
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim()
}

function optionalString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined
  }

  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

function parseSuggestion(text: string): SeoSuggestion {
  const normalizedText = stripCodeFence(text)
  try {
    const parsed = JSON.parse(normalizedText) as Record<string, unknown>
    return {
      title: optionalString(parsed.title),
      description: optionalString(parsed.description),
      og_title: optionalString(parsed.og_title),
      og_description: optionalString(parsed.og_description),
    }
  } catch {
    return {
      description: normalizedText,
    }
  }
}

function aiErrorLabel(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.status === 403 || error.code === 'PERMISSION_DENIED') {
      return `Permission denied: ${error.detail}`
    }

    if (error.status === 400 || error.code?.includes('AI_')) {
      return `Provider unavailable: ${error.detail}`
    }
  }

  return `Backend failure: ${asUserMessage(error)}`
}

async function generateSuggestion(): Promise<void> {
  if (props.readOnly) {
    return
  }

  aiErrorMessage.value = null
  suggestion.value = null
  generating.value = true

  try {
    const response = await generateAiText({
      scope: 'seo',
      input: buildAiInput(),
      instructions: 'Draft concise SEO/social metadata for this CMS entry. Return only JSON with keys title, description, og_title, and og_description. Do not schedule, publish, or claim the entry is live.',
      temperature: 0.4,
      max_output_tokens: 320,
    })
    const nextSuggestion = parseSuggestion(response.text)
    suggestion.value = Object.values(nextSuggestion).some((value) => typeof value === 'string' && value.length > 0)
      ? nextSuggestion
      : { description: response.text.trim() }
  } catch (error) {
    aiErrorMessage.value = aiErrorLabel(error)
  } finally {
    generating.value = false
  }
}

function acceptSuggestion(): void {
  if (props.readOnly || suggestion.value === null) {
    return
  }

  emit('update:modelValue', {
    ...props.modelValue,
    title: suggestion.value.title ?? props.modelValue.title,
    description: suggestion.value.description ?? props.modelValue.description,
    og_title: suggestion.value.og_title ?? props.modelValue.og_title,
    og_description: suggestion.value.og_description ?? props.modelValue.og_description,
  })
  suggestion.value = null
}

function dismissSuggestion(): void {
  suggestion.value = null
  aiErrorMessage.value = null
}
</script>

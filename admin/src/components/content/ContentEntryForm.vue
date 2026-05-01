<template>
  <form class="form-stack" @submit.prevent="handleSubmit">
    <Message v-if="errorMessage" severity="error" :closable="false">
      {{ errorMessage }}
    </Message>
    <Message v-if="localErrorMessage" severity="warn" :closable="false">
      {{ localErrorMessage }}
    </Message>
    <Message v-if="readOnly" severity="info" :closable="false">
      You can view this entry, but you do not have permission to save changes.
    </Message>
    <Message v-else-if="cannotSubmitPublishedStatus" severity="warn" :closable="false">
      Publishing entries requires the content.entries.publish permission.
    </Message>

    <div class="form-grid">
      <div class="field">
        <label for="entry-status">Status</label>
        <Select
          id="entry-status"
          v-model="formState.status"
          :options="statusOptions"
          optionLabel="label"
          optionValue="value"
          :disabled="formDisabled || statusSelectDisabled"
        />
      </div>

      <div class="field">
        <label for="entry-slug">Slug override</label>
        <InputText
          id="entry-slug"
          v-model.trim="formState.slug"
          :disabled="formDisabled"
          placeholder="Leave blank to auto-generate"
        />
        <small class="muted">Leave empty to auto-generate a slug from the entry content.</small>
      </div>
    </div>

    <div
      v-for="fieldDefinition in contentType.field_definitions"
      :key="fieldDefinition.name"
      class="field"
      :class="{ 'field--full': isWideField(fieldDefinition.kind) }"
    >
      <label :for="fieldId(fieldDefinition.name)">
        {{ fieldDefinition.label }}
        <span v-if="fieldDefinition.required">*</span>
      </label>

      <InputText
        v-if="fieldDefinition.kind === 'text'"
        :id="fieldId(fieldDefinition.name)"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
      />

      <Textarea
        v-else-if="fieldDefinition.kind === 'long_text'"
        :id="fieldId(fieldDefinition.name)"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
        rows="6"
        autoResize
      />

      <RichTextEditor
        v-else-if="fieldDefinition.kind === 'rich_text'"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
      />

      <InputNumber
        v-else-if="fieldDefinition.kind === 'integer'"
        :id="fieldId(fieldDefinition.name)"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
        :min="fieldDefinition.minimum ?? undefined"
        :max="fieldDefinition.maximum ?? undefined"
        :useGrouping="false"
        inputMode="numeric"
      />

      <InputNumber
        v-else-if="fieldDefinition.kind === 'number'"
        :id="fieldId(fieldDefinition.name)"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
        :min="fieldDefinition.minimum ?? undefined"
        :max="fieldDefinition.maximum ?? undefined"
        :useGrouping="false"
        inputMode="decimal"
      />

      <div v-else-if="fieldDefinition.kind === 'boolean'" class="field__checkbox-row">
        <Checkbox
          :inputId="fieldId(fieldDefinition.name)"
          v-model="formState.fields[fieldDefinition.name]"
          binary
          :disabled="formDisabled"
        />
        <label :for="fieldId(fieldDefinition.name)">Enabled</label>
      </div>

      <InputText
        v-else-if="fieldDefinition.kind === 'date'"
        :id="fieldId(fieldDefinition.name)"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
        type="date"
      />

      <InputText
        v-else-if="fieldDefinition.kind === 'datetime'"
        :id="fieldId(fieldDefinition.name)"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
        type="datetime-local"
      />

      <Textarea
        v-else
        :id="fieldId(fieldDefinition.name)"
        v-model="formState.fields[fieldDefinition.name]"
        :disabled="formDisabled"
        rows="8"
        autoResize
        spellcheck="false"
      />

      <small v-if="fieldHint(fieldDefinition.kind)" class="muted">
        {{ fieldHint(fieldDefinition.kind) }}
      </small>
    </div>

    <div class="inline-actions">
      <Button
        type="submit"
        :label="submitLabel"
        icon="pi pi-save"
        :loading="submitting"
        :disabled="formDisabled || cannotSubmitPublishedStatus"
      />
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'

import type {
  ContentEntryResponse,
  ContentEntryStatus,
  ContentFieldDefinition,
  ContentTypeResponse,
} from '@/api/types'
import RichTextEditor from '@/components/content/RichTextEditor.vue'
import {
  ContentEntryFormError,
  buildContentEntryFormState,
  serializeContentEntryFormState,
} from '@/features/content/form'

const props = withDefaults(
  defineProps<{
    contentType: ContentTypeResponse
    entry?: ContentEntryResponse | null
    errorMessage?: string | null
    submitting?: boolean
    readOnly?: boolean
    canPublish?: boolean
  }>(),
  {
    entry: null,
    errorMessage: null,
    submitting: false,
    readOnly: false,
    canPublish: false,
  },
)

const emit = defineEmits<{
  submit: [payload: { slug: string | null; status: ContentEntryStatus; payload: Record<string, unknown> }]
}>()

const baseStatusOptions: Array<{ label: string; value: ContentEntryStatus }> = [
  { label: 'Draft', value: 'draft' },
  { label: 'Published', value: 'published' },
  { label: 'Archived', value: 'archived' },
]

const formState = reactive(buildContentEntryFormState(props.contentType, props.entry))
const localErrorMessage = ref<string | null>(null)

const formDisabled = computed(() => props.submitting || props.readOnly)
const statusOptions = computed(() =>
  baseStatusOptions.filter((option) => option.value !== 'published' || props.canPublish || props.entry?.status === 'published'),
)
const cannotSubmitPublishedStatus = computed(() => formState.status === 'published' && !props.canPublish)
const statusSelectDisabled = computed(() => !props.canPublish && props.entry?.status === 'published')

function resetFormState(): void {
  const nextState = buildContentEntryFormState(props.contentType, props.entry)
  formState.slug = nextState.slug
  formState.status = nextState.status
  formState.fields = nextState.fields
  localErrorMessage.value = null
}

watch(
  () => [props.contentType.id, props.entry?.id, props.entry?.updated_at],
  () => {
    resetFormState()
  },
  { immediate: false },
)

function fieldId(fieldName: string): string {
  return `entry-field-${fieldName}`
}

function fieldHint(kind: ContentFieldDefinition['kind']): string | null {
  if (kind === 'rich_text') {
    return 'Allowed HTML is limited to the StarterKit-compatible Pragma rich-text contract.'
  }

  if (kind === 'json') {
    return 'Enter valid JSON for this field.'
  }

  return null
}

function isWideField(kind: ContentFieldDefinition['kind']): boolean {
  return kind === 'long_text' || kind === 'rich_text' || kind === 'json'
}

async function handleSubmit(): Promise<void> {
  localErrorMessage.value = null

  if (props.readOnly) {
    localErrorMessage.value = 'You do not have permission to save content entries.'
    return
  }

  if (cannotSubmitPublishedStatus.value) {
    localErrorMessage.value = 'Publishing entries requires the content.entries.publish permission.'
    return
  }

  try {
    emit('submit', serializeContentEntryFormState(props.contentType, formState))
  } catch (error) {
    if (error instanceof ContentEntryFormError) {
      localErrorMessage.value = error.message
      return
    }
    throw error
  }
}

const submitLabel = computed(() => (props.entry === null ? 'Create entry' : 'Save changes'))
</script>

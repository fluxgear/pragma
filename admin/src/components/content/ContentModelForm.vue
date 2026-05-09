<template>
  <form class="content-model-form" @submit.prevent="handleSubmit">
    <Message v-if="errorMessage" severity="error" :closable="false">
      {{ errorMessage }}
    </Message>
    <Message v-if="localErrorMessage" severity="warn" :closable="false">
      {{ localErrorMessage }}
    </Message>
    <Message v-if="!canManage" severity="info" :closable="false">
      You can view this model, but saving requires content.types.manage.
    </Message>
    <Message v-if="mode === 'edit' && (model?.entry_count ?? 0) > 0" severity="warn" :closable="false">
      This model has {{ model?.entry_count }} existing entr{{ model?.entry_count === 1 ? 'y' : 'ies' }}.
      Removing fields, renaming field keys, changing field types, or tightening validation may be blocked if entries would become invalid.
    </Message>

    <div class="content-model-form__layout">
      <div class="content-model-form__editor form-stack">
        <Card>
          <template #title>Model details</template>
          <template #content>
            <div class="form-grid">
              <div class="field">
                <label for="content-model-name">Name</label>
                <InputText
                  id="content-model-name"
                  v-model.trim="formState.name"
                  data-testid="model-name"
                  :disabled="formDisabled"
                  @update:modelValue="markSlugEditedIfNeeded"
                />
                <small class="muted">A human-readable name for administrators and editors.</small>
                <small v-if="detailErrors.name" class="content-model-builder__error">{{ detailErrors.name }}</small>
              </div>

              <div class="field">
                <label for="content-model-slug">Slug</label>
                <InputText
                  id="content-model-slug"
                  v-model.trim="formState.slug"
                  data-testid="model-slug"
                  :disabled="formDisabled"
                  placeholder="Leave blank to auto-generate"
                  @input="slugManuallyEdited = true"
                />
                <small class="muted">Optional API-facing identifier. Use lowercase letters, numbers, and hyphens.</small>
                <small v-if="detailErrors.slug" class="content-model-builder__error">{{ detailErrors.slug }}</small>
              </div>

              <div class="field field--full">
                <label for="content-model-description">Description</label>
                <Textarea
                  id="content-model-description"
                  v-model="formState.description"
                  data-testid="model-description"
                  :disabled="formDisabled"
                  rows="3"
                  autoResize
                  placeholder="Explain when editors should use this model."
                />
              </div>
            </div>
          </template>
        </Card>

        <Card>
          <template #title>Field builder</template>
          <template #content>
            <ContentModelFieldBuilder
              v-model="formState.field_definitions"
              @validation-change="fieldValidation = $event"
            />
          </template>
        </Card>
      </div>

      <aside class="content-model-preview" aria-labelledby="model-preview-title">
        <div class="content-model-preview__header">
          <div>
            <p class="content-model-preview__eyebrow">Generated preview</p>
            <h2 id="model-preview-title">{{ previewTitle }}</h2>
          </div>
          <Tag severity="info" value="Read-only" />
        </div>
        <p class="muted">
          This preview uses the unsaved draft fields and shows how entry authors will encounter the generated form.
        </p>

        <div v-if="formState.field_definitions.length === 0" class="content-model-preview__empty">
          Add fields to preview the generated entry form.
        </div>
        <div v-else class="form-stack">
          <div
            v-for="field in formState.field_definitions"
            :key="field.name"
            class="field"
            :class="{ 'field--full': isWideField(field.kind) }"
          >
            <label :for="`preview-${field.name}`">
              {{ field.label || 'Untitled field' }}
              <span v-if="field.required">*</span>
            </label>
            <InputText
              v-if="field.kind === 'text'"
              :id="`preview-${field.name}`"
              :modelValue="previewValue(field)"
              disabled
            />
            <Textarea
              v-else-if="field.kind === 'long_text' || field.kind === 'rich_text' || field.kind === 'json'"
              :id="`preview-${field.name}`"
              :modelValue="previewValue(field)"
              disabled
              :rows="field.kind === 'json' ? 5 : 4"
            />
            <InputNumber
              v-else-if="field.kind === 'integer' || field.kind === 'number'"
              :id="`preview-${field.name}`"
              :modelValue="numericPreviewValue(field.default_value)"
              disabled
              :useGrouping="false"
            />
            <div v-else-if="field.kind === 'boolean'" class="field__checkbox-row">
              <Checkbox :inputId="`preview-${field.name}`" :modelValue="field.default_value === true" disabled binary />
              <label :for="`preview-${field.name}`">Enabled</label>
            </div>
            <InputText
              v-else
              :id="`preview-${field.name}`"
              :modelValue="previewValue(field)"
              disabled
              :type="field.kind === 'date' ? 'date' : 'datetime-local'"
            />
            <small v-if="field.help_text" class="muted">{{ field.help_text }}</small>
            <small class="muted">{{ fieldTypeLabel(field.kind) }}</small>
          </div>
        </div>
      </aside>
    </div>

    <div class="content-model-form__footer">
      <div v-if="mode === 'edit'" class="content-model-form__danger-zone">
        <strong>Danger zone</strong>
        <p class="muted">
          Delete is only available for models with zero entries. Models with entries must stay readable.
        </p>
        <Button
          type="button"
          label="Delete model"
          icon="pi pi-trash"
          severity="danger"
          variant="outlined"
          data-testid="delete-model"
          :disabled="formDisabled || !model?.can_delete"
          :title="deleteDisabledReason"
          @click="$emit('delete')"
        />
      </div>

      <div class="content-model-form__primary-actions inline-actions">
        <Button type="button" label="Cancel" severity="secondary" variant="outlined" @click="$emit('cancel')" />
        <Button
          type="submit"
          :label="mode === 'edit' ? 'Save changes' : 'Create model'"
          icon="pi pi-save"
          data-testid="save-model"
          :loading="submitting"
          :disabled="formDisabled || !formValid"
        />
      </div>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import type {
  ContentFieldDefinition,
  ContentTypeCreateRequest,
  ContentTypeResponse,
  ContentTypeUpdateRequest,
} from '@/api/types'
import ContentModelFieldBuilder from '@/components/content/ContentModelFieldBuilder.vue'

interface ContentModelFieldBuilderValidation {
  valid: boolean
  errors: Array<{ index: number; property: string; message: string }>
}

const props = withDefaults(
  defineProps<{
    mode: 'create' | 'edit'
    model?: ContentTypeResponse | null
    errorMessage?: string | null
    submitting?: boolean
    canManage?: boolean
  }>(),
  {
    model: null,
    errorMessage: null,
    submitting: false,
    canManage: true,
  },
)

const emit = defineEmits<{
  submit: [payload: ContentTypeCreateRequest | ContentTypeUpdateRequest]
  cancel: []
  delete: []
}>()

const formState = reactive({
  name: '',
  slug: '',
  description: '',
  field_definitions: [] as ContentFieldDefinition[],
})
const slugManuallyEdited = ref(false)
const localErrorMessage = ref<string | null>(null)
const fieldValidation = ref<ContentModelFieldBuilderValidation>({ valid: false, errors: [] })

const formDisabled = computed(() => props.submitting || !props.canManage)
const previewTitle = computed(() => formState.name.trim() || 'Untitled model')
const detailErrors = computed(() => {
  const errors: { name?: string; slug?: string } = {}
  if (formState.name.trim().length === 0) {
    errors.name = 'Name is required.'
  }
  if (formState.slug.trim().length > 0 && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(formState.slug.trim())) {
    errors.slug = 'Use lowercase letters, numbers, and hyphens.'
  }
  return errors
})
const formValid = computed(
  () => Object.keys(detailErrors.value).length === 0 && fieldValidation.value.valid,
)
const deleteDisabledReason = computed(() => {
  if (!props.model) {
    return undefined
  }
  if (props.model.can_delete) {
    return undefined
  }
  return `Cannot delete while ${props.model.entry_count} entr${props.model.entry_count === 1 ? 'y' : 'ies'} exist.`
})

watch(
  () => [props.mode, props.model?.id, props.model?.updated_at],
  () => {
    resetFormState()
  },
  { immediate: true },
)

watch(
  () => formState.name,
  (nextName) => {
    if (props.mode === 'create' && !slugManuallyEdited.value) {
      formState.slug = slugify(nextName)
    }
  },
)

function resetFormState(): void {
  if (props.mode === 'edit' && props.model) {
    formState.name = props.model.name
    formState.slug = props.model.slug
    formState.description = props.model.description ?? ''
    formState.field_definitions = cloneFields(props.model.field_definitions)
  } else {
    formState.name = ''
    formState.slug = ''
    formState.description = ''
    formState.field_definitions = [
      {
        kind: 'text',
        name: 'title',
        label: 'Title',
        required: true,
        min_length: null,
        max_length: 160,
        help_text: 'Short title editors can recognize in content lists.',
      },
    ]
  }
  slugManuallyEdited.value = props.mode === 'edit'
  localErrorMessage.value = null
}

function handleSubmit(): void {
  localErrorMessage.value = null

  if (!props.canManage) {
    localErrorMessage.value = 'You do not have permission to save content models.'
    return
  }

  if (!formValid.value) {
    localErrorMessage.value = 'Fix the highlighted model and field errors before saving.'
    return
  }

  emit('submit', {
    name: formState.name.trim(),
    slug: formState.slug.trim() || null,
    description: formState.description.trim() || null,
    field_definitions: cloneFields(formState.field_definitions),
  })
}

function markSlugEditedIfNeeded(): void {
  if (props.mode === 'edit') {
    slugManuallyEdited.value = true
  }
}

function cloneFields(fields: ContentFieldDefinition[]): ContentFieldDefinition[] {
  return fields.map((field) => ({ ...field }))
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function fieldTypeLabel(kind: ContentFieldDefinition['kind']): string {
  return kind.replace('_', ' ')
}

function isWideField(kind: ContentFieldDefinition['kind']): boolean {
  return kind === 'long_text' || kind === 'rich_text' || kind === 'json'
}

function previewValue(field: ContentFieldDefinition): string {
  const value = field.default_value
  if (value === undefined || value === null) {
    return ''
  }
  if (field.kind === 'json') {
    return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  }
  return String(value)
}

function numericPreviewValue(value: unknown): number | null {
  return typeof value === 'number' && !Number.isNaN(value) ? value : null
}
</script>

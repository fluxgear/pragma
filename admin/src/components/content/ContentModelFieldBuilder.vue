<template>
  <section class="content-model-builder" aria-labelledby="field-builder-title">
    <div class="content-model-builder__header">
      <div>
        <h3 id="field-builder-title">Fields</h3>
        <p class="muted">
          Add fields in the order editors should complete them. Field keys are stable schema identifiers.
        </p>
      </div>
      <Button
        type="button"
        label="Add field"
        icon="pi pi-plus"
        data-testid="field-builder-add"
        @click="addField"
      />
    </div>

    <Message v-if="modelValue.length === 0" severity="warn" :closable="false">
      Add at least one field so editors have a generated entry form to use.
    </Message>

    <ol class="content-model-builder__list" aria-label="Content model fields">
      <li
        v-for="(field, index) in modelValue"
        :key="field.name || index"
        class="content-model-builder__field-card"
        :data-testid="`field-card-${index}`"
      >
        <div class="content-model-builder__field-header">
          <div>
            <span class="content-model-builder__field-position">Field {{ index + 1 }}</span>
            <strong>{{ field.label || 'Untitled field' }}</strong>
            <span class="muted code-chip">{{ field.name || 'missing_key' }}</span>
          </div>
          <div class="content-model-builder__field-actions" aria-label="Field actions">
            <Button
              type="button"
              label="Move up"
              icon="pi pi-arrow-up"
              severity="secondary"
              variant="outlined"
              size="small"
              :disabled="index === 0"
              :data-testid="`field-move-up-${index}`"
              @click="moveField(index, index - 1)"
            />
            <Button
              type="button"
              label="Move down"
              icon="pi pi-arrow-down"
              severity="secondary"
              variant="outlined"
              size="small"
              :disabled="index === modelValue.length - 1"
              :data-testid="`field-move-down-${index}`"
              @click="moveField(index, index + 1)"
            />
            <Button
              type="button"
              label="Remove"
              icon="pi pi-trash"
              severity="danger"
              variant="outlined"
              size="small"
              :data-testid="`field-delete-${index}`"
              @click="removeField(index)"
            />
          </div>
        </div>

        <div class="form-grid">
          <div class="field">
            <label :for="fieldInputId(index, 'kind')">Field type</label>
            <select
              :id="fieldInputId(index, 'kind')"
              class="content-model-builder__native-control"
              :value="field.kind"
              :data-testid="`field-kind-${index}`"
              @change="updateKind(index, ($event.target as HTMLSelectElement).value as ContentModelFieldKind)"
            >
              <option v-for="option in fieldKindOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>

          <div class="field">
            <label :for="fieldInputId(index, 'label')">Label</label>
            <InputText
              :id="fieldInputId(index, 'label')"
              :modelValue="field.label"
              :data-testid="`field-label-${index}`"
              @update:modelValue="updateField(index, { label: String($event) })"
            />
            <small class="muted">Shown to editors in entry forms.</small>
            <small v-if="fieldErrors(index, 'label').length > 0" class="content-model-builder__error">
              {{ fieldErrors(index, 'label').join(' ') }}
            </small>
          </div>

          <div class="field">
            <label :for="fieldInputId(index, 'name')">Field key</label>
            <InputText
              :id="fieldInputId(index, 'name')"
              :modelValue="field.name"
              :data-testid="`field-name-${index}`"
              placeholder="body"
              @update:modelValue="updateField(index, { name: normalizeKeyInput(String($event)) })"
            />
            <small class="muted">Use lowercase letters, numbers, and underscores. This key identifies stored entry values.</small>
            <small v-if="fieldErrors(index, 'name').length > 0" class="content-model-builder__error">
              {{ fieldErrors(index, 'name').join(' ') }}
            </small>
          </div>

          <div class="field">
            <label :for="fieldInputId(index, 'required')">Required</label>
            <div class="field__checkbox-row">
              <Checkbox
                :inputId="fieldInputId(index, 'required')"
                :modelValue="field.required"
                binary
                :data-testid="`field-required-${index}`"
                @update:modelValue="updateField(index, { required: Boolean($event) })"
              />
              <span class="muted">Editors must complete this field.</span>
            </div>
          </div>

          <div class="field field--full">
            <label :for="fieldInputId(index, 'help')">Help text</label>
            <Textarea
              :id="fieldInputId(index, 'help')"
              :modelValue="field.help_text ?? ''"
              :data-testid="`field-help-${index}`"
              rows="2"
              autoResize
              placeholder="Optional guidance for editors"
              @update:modelValue="updateField(index, { help_text: blankToNull(String($event)) })"
            />
          </div>

          <div class="field field--full">
            <label :for="fieldInputId(index, 'default')">Default value</label>
            <Textarea
              v-if="field.kind === 'json'"
              :id="fieldInputId(index, 'default')"
              :modelValue="defaultInputValue(field)"
              :data-testid="`field-default-${index}`"
              rows="4"
              autoResize
              spellcheck="false"
              placeholder='{"featured": true}'
              @update:modelValue="updateDefault(index, String($event))"
            />
            <select
              v-else-if="field.kind === 'boolean'"
              :id="fieldInputId(index, 'default')"
              class="content-model-builder__native-control"
              :value="booleanDefaultInputValue(field.default_value)"
              :data-testid="`field-default-${index}`"
              @change="updateBooleanDefault(index, ($event.target as HTMLSelectElement).value)"
            >
              <option value="">No default</option>
              <option value="true">Checked</option>
              <option value="false">Unchecked</option>
            </select>
            <InputText
              v-else
              :id="fieldInputId(index, 'default')"
              :modelValue="defaultInputValue(field)"
              :data-testid="`field-default-${index}`"
              :placeholder="defaultPlaceholder(field.kind)"
              @update:modelValue="updateDefault(index, String($event))"
            />
            <small class="muted">Optional. Required fields on models with entries need a valid default before saving.</small>
            <small v-if="fieldErrors(index, 'default_value').length > 0" class="content-model-builder__error">
              {{ fieldErrors(index, 'default_value').join(' ') }}
            </small>
          </div>

          <template v-if="isTextLike(field.kind)">
            <div class="field">
              <label :for="fieldInputId(index, 'min-length')">Minimum length</label>
              <InputNumber
                :id="fieldInputId(index, 'min-length')"
                :modelValue="textMinLength(field)"
                :data-testid="`field-min-length-${index}`"
                :min="0"
                :useGrouping="false"
                inputMode="numeric"
                @update:modelValue="updateField(index, { min_length: numberOrNull($event) })"
              />
            </div>
            <div class="field">
              <label :for="fieldInputId(index, 'max-length')">Maximum length</label>
              <InputNumber
                :id="fieldInputId(index, 'max-length')"
                :modelValue="textMaxLength(field)"
                :data-testid="`field-max-length-${index}`"
                :min="0"
                :useGrouping="false"
                inputMode="numeric"
                @update:modelValue="updateField(index, { max_length: numberOrNull($event) })"
              />
              <small v-if="fieldErrors(index, 'length').length > 0" class="content-model-builder__error">
                {{ fieldErrors(index, 'length').join(' ') }}
              </small>
            </div>
          </template>

          <template v-if="isNumeric(field.kind)">
            <div class="field">
              <label :for="fieldInputId(index, 'minimum')">Minimum value</label>
              <InputNumber
                :id="fieldInputId(index, 'minimum')"
                :modelValue="numericMinimum(field)"
                :data-testid="`field-minimum-${index}`"
                :useGrouping="false"
                :inputMode="field.kind === 'integer' ? 'numeric' : 'decimal'"
                @update:modelValue="updateField(index, { minimum: numberOrNull($event) })"
              />
            </div>
            <div class="field">
              <label :for="fieldInputId(index, 'maximum')">Maximum value</label>
              <InputNumber
                :id="fieldInputId(index, 'maximum')"
                :modelValue="numericMaximum(field)"
                :data-testid="`field-maximum-${index}`"
                :useGrouping="false"
                :inputMode="field.kind === 'integer' ? 'numeric' : 'decimal'"
                @update:modelValue="updateField(index, { maximum: numberOrNull($event) })"
              />
              <small v-if="fieldErrors(index, 'range').length > 0" class="content-model-builder__error">
                {{ fieldErrors(index, 'range').join(' ') }}
              </small>
            </div>
          </template>
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Textarea from 'primevue/textarea'

import type {
  ContentFieldDefinition,
  IntegerFieldDefinition,
  NumberFieldDefinition,
  TextFieldDefinition,
} from '@/api/types'

type ContentModelFieldKind = ContentFieldDefinition['kind']

type FieldErrorProperty =
  | 'label'
  | 'name'
  | 'default_value'
  | 'length'
  | 'range'
  | 'fields'

interface ContentModelFieldBuilderError {
  index: number
  property: FieldErrorProperty
  message: string
}

interface ContentModelFieldBuilderValidation {
  valid: boolean
  errors: ContentModelFieldBuilderError[]
}

const props = defineProps<{
  modelValue: ContentFieldDefinition[]
}>()

const emit = defineEmits<{
  'update:modelValue': [fields: ContentFieldDefinition[]]
  'validation-change': [validation: ContentModelFieldBuilderValidation]
}>()

const fieldKindOptions: Array<{ label: string; value: ContentModelFieldKind }> = [
  { label: 'Short text', value: 'text' },
  { label: 'Long text', value: 'long_text' },
  { label: 'Rich text', value: 'rich_text' },
  { label: 'Integer', value: 'integer' },
  { label: 'Number', value: 'number' },
  { label: 'Boolean', value: 'boolean' },
  { label: 'Date', value: 'date' },
  { label: 'Date and time', value: 'datetime' },
  { label: 'JSON', value: 'json' },
]

const keyPattern = /^[a-z][a-z0-9_]*$/
const reservedKeys = new Set(['id', 'slug', 'status', 'created_at', 'updated_at', 'published_at'])

const validation = computed<ContentModelFieldBuilderValidation>(() => {
  const errors: ContentModelFieldBuilderError[] = []
  const seenNames = new Map<string, number>()

  if (props.modelValue.length === 0) {
    errors.push({ index: -1, property: 'fields', message: 'Add at least one field.' })
  }

  props.modelValue.forEach((field, index) => {
    const label = field.label.trim()
    const name = field.name.trim()

    if (label.length === 0) {
      errors.push({ index, property: 'label', message: 'Label is required.' })
    }

    if (name.length === 0) {
      errors.push({ index, property: 'name', message: 'Field key is required.' })
    } else if (!keyPattern.test(name)) {
      errors.push({ index, property: 'name', message: 'Use lowercase letters, numbers, and underscores, starting with a letter.' })
    } else if (reservedKeys.has(name)) {
      errors.push({ index, property: 'name', message: 'This key is reserved by content entries.' })
    }

    const firstSeenIndex = seenNames.get(name)
    if (name.length > 0 && firstSeenIndex !== undefined) {
      errors.push({ index, property: 'name', message: `Field key duplicates field ${firstSeenIndex + 1}.` })
    }
    if (name.length > 0) {
      seenNames.set(name, index)
    }

    if (isTextLike(field.kind)) {
      const minLength = textMinLength(field)
      const maxLength = textMaxLength(field)
      if (minLength !== null && minLength < 0) {
        errors.push({ index, property: 'length', message: 'Minimum length cannot be negative.' })
      }
      if (maxLength !== null && maxLength < 0) {
        errors.push({ index, property: 'length', message: 'Maximum length cannot be negative.' })
      }
      if (minLength !== null && maxLength !== null && minLength > maxLength) {
        errors.push({ index, property: 'length', message: 'Minimum length cannot exceed maximum length.' })
      }
    }

    if (isNumeric(field.kind)) {
      const minimum = numericMinimum(field)
      const maximum = numericMaximum(field)
      if (minimum !== null && maximum !== null && minimum > maximum) {
        errors.push({ index, property: 'range', message: 'Minimum value cannot exceed maximum value.' })
      }
    }

    errors.push(...defaultValueErrors(field, index))
  })

  return { valid: errors.length === 0, errors }
})

watch(
  validation,
  (nextValidation) => {
    emit('validation-change', nextValidation)
  },
  { immediate: true },
)

function emitFields(fields: ContentFieldDefinition[]): void {
  emit('update:modelValue', fields)
}

function addField(): void {
  const nextIndex = props.modelValue.length + 1
  const baseName = `field_${nextIndex}`
  const existingNames = new Set(props.modelValue.map((field) => field.name))
  let name = baseName
  let suffix = nextIndex

  while (existingNames.has(name)) {
    suffix += 1
    name = `field_${suffix}`
  }

  emitFields([
    ...props.modelValue,
    {
      kind: 'text',
      label: 'New field',
      name,
      required: false,
      min_length: null,
      max_length: null,
      help_text: null,
    },
  ])
}

function moveField(fromIndex: number, toIndex: number): void {
  if (toIndex < 0 || toIndex >= props.modelValue.length) {
    return
  }

  const fields = [...props.modelValue]
  const [field] = fields.splice(fromIndex, 1)
  fields.splice(toIndex, 0, field)
  emitFields(fields)
}

function removeField(index: number): void {
  emitFields(props.modelValue.filter((_, fieldIndex) => fieldIndex !== index))
}

function updateField(index: number, patch: Partial<ContentFieldDefinition>): void {
  emitFields(props.modelValue.map((field, fieldIndex) => (fieldIndex === index ? sanitizeField({ ...field, ...patch }) : field)))
}

function updateKind(index: number, kind: ContentModelFieldKind): void {
  const currentField = props.modelValue[index]
  if (!currentField) {
    return
  }

  const base = {
    name: currentField.name,
    label: currentField.label,
    required: currentField.required,
    help_text: currentField.help_text ?? null,
  }

  const nextField: ContentFieldDefinition = createFieldForKind(kind, base)
  emitFields(props.modelValue.map((field, fieldIndex) => (fieldIndex === index ? nextField : field)))
}

function updateDefault(index: number, rawValue: string): void {
  const field = props.modelValue[index]
  if (!field) {
    return
  }

  const trimmedValue = rawValue.trim()
  if (trimmedValue.length === 0) {
    updateField(index, { default_value: undefined })
    return
  }

  if (field.kind === 'integer') {
    updateField(index, { default_value: Number.parseInt(trimmedValue, 10) })
    return
  }

  if (field.kind === 'number') {
    updateField(index, { default_value: Number(trimmedValue) })
    return
  }

  if (field.kind === 'json') {
    try {
      updateField(index, { default_value: JSON.parse(trimmedValue) })
    } catch {
      updateField(index, { default_value: rawValue })
    }
    return
  }

  updateField(index, { default_value: rawValue })
}

function updateBooleanDefault(index: number, rawValue: string): void {
  if (rawValue === 'true') {
    updateField(index, { default_value: true })
    return
  }

  if (rawValue === 'false') {
    updateField(index, { default_value: false })
    return
  }

  updateField(index, { default_value: undefined })
}

function createFieldForKind(
  kind: ContentModelFieldKind,
  base: Pick<ContentFieldDefinition, 'name' | 'label' | 'required'> & { help_text?: string | null },
): ContentFieldDefinition {
  if (kind === 'text' || kind === 'long_text' || kind === 'rich_text') {
    return { ...base, kind, min_length: null, max_length: null }
  }

  if (kind === 'integer') {
    return { ...base, kind, minimum: null, maximum: null }
  }

  if (kind === 'number') {
    return { ...base, kind, minimum: null, maximum: null }
  }

  return { ...base, kind }
}

function sanitizeField(field: ContentFieldDefinition): ContentFieldDefinition {
  if (field.kind === 'text' || field.kind === 'long_text' || field.kind === 'rich_text') {
    return {
      ...field,
      min_length: textMinLength(field),
      max_length: textMaxLength(field),
    }
  }

  if (field.kind === 'integer' || field.kind === 'number') {
    return {
      ...field,
      minimum: numericMinimum(field),
      maximum: numericMaximum(field),
    }
  }

  return field
}

function defaultValueErrors(field: ContentFieldDefinition, index: number): ContentModelFieldBuilderError[] {
  const value = field.default_value
  if (value === undefined || value === null || value === '') {
    return []
  }

  if (field.kind === 'integer') {
    if (typeof value !== 'number' || !Number.isInteger(value)) {
      return [{ index, property: 'default_value', message: 'Default must be a whole number.' }]
    }
    return []
  }

  if (field.kind === 'number') {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return [{ index, property: 'default_value', message: 'Default must be a number.' }]
    }
    return []
  }

  if (field.kind === 'boolean') {
    if (typeof value !== 'boolean') {
      return [{ index, property: 'default_value', message: 'Default must be checked or unchecked.' }]
    }
    return []
  }

  if (field.kind === 'json' && typeof value === 'string') {
    return [{ index, property: 'default_value', message: 'Default JSON must parse successfully.' }]
  }

  return []
}

function fieldErrors(index: number, property: FieldErrorProperty): string[] {
  return validation.value.errors
    .filter((error) => error.index === index && error.property === property)
    .map((error) => error.message)
}

function fieldInputId(index: number, fieldName: string): string {
  return `model-field-${index}-${fieldName}`
}

function isTextLike(kind: ContentModelFieldKind): boolean {
  return kind === 'text' || kind === 'long_text' || kind === 'rich_text'
}

function isNumeric(kind: ContentModelFieldKind): boolean {
  return kind === 'integer' || kind === 'number'
}

function textMinLength(field: ContentFieldDefinition): number | null {
  return isTextLike(field.kind) ? ((field as TextFieldDefinition).min_length ?? null) : null
}

function textMaxLength(field: ContentFieldDefinition): number | null {
  return isTextLike(field.kind) ? ((field as TextFieldDefinition).max_length ?? null) : null
}

function numericMinimum(field: ContentFieldDefinition): number | null {
  return isNumeric(field.kind) ? ((field as IntegerFieldDefinition | NumberFieldDefinition).minimum ?? null) : null
}

function numericMaximum(field: ContentFieldDefinition): number | null {
  return isNumeric(field.kind) ? ((field as IntegerFieldDefinition | NumberFieldDefinition).maximum ?? null) : null
}

function numberOrNull(value: number | null | undefined): number | null {
  return typeof value === 'number' && !Number.isNaN(value) ? value : null
}

function blankToNull(value: string): string | null {
  const trimmedValue = value.trim()
  return trimmedValue.length > 0 ? trimmedValue : null
}

function normalizeKeyInput(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_')
}

function defaultInputValue(field: ContentFieldDefinition): string {
  const value = field.default_value
  if (value === undefined || value === null) {
    return ''
  }

  if (field.kind === 'json') {
    return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  }

  return String(value)
}

function booleanDefaultInputValue(value: unknown): string {
  if (value === true) {
    return 'true'
  }
  if (value === false) {
    return 'false'
  }
  return ''
}

function defaultPlaceholder(kind: ContentModelFieldKind): string {
  if (kind === 'integer') {
    return '0'
  }
  if (kind === 'number') {
    return '0.0'
  }
  if (kind === 'date') {
    return '2026-05-06'
  }
  if (kind === 'datetime') {
    return '2026-05-06T09:00'
  }
  return 'Optional default'
}
</script>

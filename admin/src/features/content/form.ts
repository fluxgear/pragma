import type {
  ContentEntryResponse,
  ContentEntryStatus,
  ContentFieldDefinition,
  ContentTypeResponse,
} from '@/api/types'

export class ContentEntryFormError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ContentEntryFormError'
  }
}

export type ContentEntryFormValue = boolean | number | string | null

export interface ContentEntryFormState {
  slug: string
  status: ContentEntryStatus
  fields: Record<string, ContentEntryFormValue>
}

const EMPTY_RICH_TEXT = ''

function toDateTimeLocalValue(value: unknown): string {
  if (typeof value !== 'string' || value.length === 0) {
    return ''
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  const year = parsed.getFullYear()
  const month = `${parsed.getMonth() + 1}`.padStart(2, '0')
  const day = `${parsed.getDate()}`.padStart(2, '0')
  const hours = `${parsed.getHours()}`.padStart(2, '0')
  const minutes = `${parsed.getMinutes()}`.padStart(2, '0')

  return `${year}-${month}-${day}T${hours}:${minutes}`
}

function buildInitialFieldValue(
  fieldDefinition: ContentFieldDefinition,
  value: unknown,
): ContentEntryFormValue {
  switch (fieldDefinition.kind) {
    case 'text':
    case 'long_text':
      return typeof value === 'string' ? value : ''
    case 'rich_text':
      return typeof value === 'string' ? value : EMPTY_RICH_TEXT
    case 'integer':
    case 'number':
      return typeof value === 'number' ? value : null
    case 'boolean':
      return typeof value === 'boolean' ? value : false
    case 'date':
      return typeof value === 'string' ? value : ''
    case 'datetime':
      return toDateTimeLocalValue(value)
    case 'json':
      return value === undefined ? '' : JSON.stringify(value, null, 2)
  }
}

function requiredFieldMessage(fieldDefinition: ContentFieldDefinition): string {
  return `${fieldDefinition.label} is required.`
}

export function isRichTextEffectivelyEmpty(value: string): boolean {
  const normalized = value
    .replace(/<br\s*\/?>/gi, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .trim()

  return normalized.length === 0
}

export function buildContentEntryFormState(
  contentType: ContentTypeResponse,
  entry: ContentEntryResponse | null = null,
): ContentEntryFormState {
  const fields = Object.fromEntries(
    contentType.field_definitions.map((fieldDefinition) => [
      fieldDefinition.name,
      buildInitialFieldValue(fieldDefinition, entry?.payload[fieldDefinition.name]),
    ]),
  )

  return {
    slug: entry?.slug ?? '',
    status: entry?.status ?? 'draft',
    fields,
  }
}

export function serializeContentEntryFormState(
  contentType: ContentTypeResponse,
  state: ContentEntryFormState,
): { slug: string | null; status: ContentEntryStatus; payload: Record<string, unknown> } {
  const payload: Record<string, unknown> = {}

  for (const fieldDefinition of contentType.field_definitions) {
    const rawValue = state.fields[fieldDefinition.name]

    switch (fieldDefinition.kind) {
      case 'text':
      case 'long_text': {
        const textValue = typeof rawValue === 'string' ? rawValue : ''
        if (textValue.length === 0) {
          if (fieldDefinition.required) {
            throw new ContentEntryFormError(requiredFieldMessage(fieldDefinition))
          }
          continue
        }
        payload[fieldDefinition.name] = textValue
        continue
      }
      case 'rich_text': {
        const htmlValue = typeof rawValue === 'string' ? rawValue : EMPTY_RICH_TEXT
        if (isRichTextEffectivelyEmpty(htmlValue)) {
          if (fieldDefinition.required) {
            throw new ContentEntryFormError(requiredFieldMessage(fieldDefinition))
          }
          continue
        }
        payload[fieldDefinition.name] = htmlValue
        continue
      }
      case 'integer': {
        if (rawValue === null || rawValue === '') {
          if (fieldDefinition.required) {
            throw new ContentEntryFormError(requiredFieldMessage(fieldDefinition))
          }
          continue
        }
        if (typeof rawValue !== 'number' || !Number.isInteger(rawValue)) {
          throw new ContentEntryFormError(`${fieldDefinition.label} must be an integer.`)
        }
        payload[fieldDefinition.name] = rawValue
        continue
      }
      case 'number': {
        if (rawValue === null || rawValue === '') {
          if (fieldDefinition.required) {
            throw new ContentEntryFormError(requiredFieldMessage(fieldDefinition))
          }
          continue
        }
        if (typeof rawValue !== 'number' || Number.isNaN(rawValue)) {
          throw new ContentEntryFormError(`${fieldDefinition.label} must be a number.`)
        }
        payload[fieldDefinition.name] = rawValue
        continue
      }
      case 'boolean': {
        payload[fieldDefinition.name] = Boolean(rawValue)
        continue
      }
      case 'date':
      case 'datetime': {
        const dateValue = typeof rawValue === 'string' ? rawValue : ''
        if (dateValue.length === 0) {
          if (fieldDefinition.required) {
            throw new ContentEntryFormError(requiredFieldMessage(fieldDefinition))
          }
          continue
        }
        payload[fieldDefinition.name] = dateValue
        continue
      }
      case 'json': {
        const jsonValue = typeof rawValue === 'string' ? rawValue.trim() : ''
        if (jsonValue.length === 0) {
          if (fieldDefinition.required) {
            throw new ContentEntryFormError(requiredFieldMessage(fieldDefinition))
          }
          continue
        }
        try {
          payload[fieldDefinition.name] = JSON.parse(jsonValue) as unknown
        } catch {
          throw new ContentEntryFormError(`${fieldDefinition.label} must contain valid JSON.`)
        }
      }
    }
  }

  return {
    slug: state.slug.trim().length > 0 ? state.slug.trim() : null,
    status: state.status,
    payload,
  }
}

export function getContentEntryDisplayTitle(entry: ContentEntryResponse): string {
  const title = entry.payload.title
  if (typeof title === 'string' && title.trim().length > 0) {
    return title
  }

  const name = entry.payload.name
  if (typeof name === 'string' && name.trim().length > 0) {
    return name
  }

  return entry.slug
}

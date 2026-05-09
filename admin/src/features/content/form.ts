import type {
  ContentEntryResponse,
  ContentEntrySeoMetadata,
  ContentEntryStatus,
  ContentFieldDefinition,
  ContentSeoRobots,
  ContentTypeResponse,
} from '@/api/types'

export class ContentEntryFormError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ContentEntryFormError'
  }
}

export type ContentEntryFormValue = boolean | number | string | null | Record<string, unknown>

export interface ContentEntrySeoMetadataFormState {
  title: string
  description: string
  canonical_url: string
  robots: ContentSeoRobots
  og_title: string
  og_description: string
  og_image: string
}

export interface ContentEntryFormState {
  slug: string
  status: ContentEntryStatus
  fields: Record<string, ContentEntryFormValue>
  seo_metadata: ContentEntrySeoMetadataFormState
  expected_version: number | null
}

export interface SerializedContentEntryFormState {
  slug: string | null
  status: ContentEntryStatus
  payload: Record<string, unknown>
  seo_metadata: ContentEntrySeoMetadata
  expected_version?: number
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
    case 'block_document':
      return value !== null && typeof value === 'object' && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : null
  }
}

function requiredFieldMessage(fieldDefinition: ContentFieldDefinition): string {
  return `${fieldDefinition.label} is required.`
}

function normalizeSeoFormValue(value: string | null | undefined): string {
  return typeof value === 'string' ? value : ''
}

export function buildContentEntrySeoMetadataFormState(
  metadata: ContentEntrySeoMetadata | null | undefined,
): ContentEntrySeoMetadataFormState {
  return {
    title: normalizeSeoFormValue(metadata?.title),
    description: normalizeSeoFormValue(metadata?.description),
    canonical_url: normalizeSeoFormValue(metadata?.canonical_url),
    robots: metadata?.robots ?? 'index',
    og_title: normalizeSeoFormValue(metadata?.og_title),
    og_description: normalizeSeoFormValue(metadata?.og_description),
    og_image: normalizeSeoFormValue(metadata?.og_image),
  }
}

function serializeOptionalSeoText(value: string): string | null {
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export function serializeContentEntrySeoMetadataFormState(
  metadata: ContentEntrySeoMetadataFormState | null | undefined,
): ContentEntrySeoMetadata {
  const normalized = metadata ?? buildContentEntrySeoMetadataFormState(null)

  return {
    title: serializeOptionalSeoText(normalized.title),
    description: serializeOptionalSeoText(normalized.description),
    canonical_url: serializeOptionalSeoText(normalized.canonical_url),
    robots: normalized.robots,
    og_title: serializeOptionalSeoText(normalized.og_title),
    og_description: serializeOptionalSeoText(normalized.og_description),
    og_image: serializeOptionalSeoText(normalized.og_image),
  }
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
    seo_metadata: buildContentEntrySeoMetadataFormState(entry?.seo_metadata),
    expected_version: entry?.version ?? null,
  }
}

export function serializeContentEntryFormState(
  contentType: ContentTypeResponse,
  state: ContentEntryFormState,
): SerializedContentEntryFormState {
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
        continue
      }
      case 'block_document': {
        if (rawValue === null || typeof rawValue !== 'object' || Array.isArray(rawValue)) {
          if (fieldDefinition.required) {
            throw new ContentEntryFormError(requiredFieldMessage(fieldDefinition))
          }
          continue
        }
        payload[fieldDefinition.name] = rawValue
      }
    }
  }

  const serialized: SerializedContentEntryFormState = {
    slug: state.slug.trim().length > 0 ? state.slug.trim() : null,
    status: state.status,
    payload,
    seo_metadata: serializeContentEntrySeoMetadataFormState(state.seo_metadata),
  }

  if (typeof state.expected_version === 'number') {
    serialized.expected_version = state.expected_version
  }

  return serialized
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

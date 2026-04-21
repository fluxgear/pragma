import { describe, expect, it } from 'vitest'

import type { ContentEntryResponse, ContentTypeResponse } from '@/api/types'
import {
  ContentEntryFormError,
  buildContentEntryFormState,
  isRichTextEffectivelyEmpty,
  serializeContentEntryFormState,
} from '@/features/content/form'

const contentType: ContentTypeResponse = {
  id: 'type-1',
  name: 'Articles',
  slug: 'articles',
  description: 'Article content',
  field_definitions: [
    {
      name: 'title',
      label: 'Title',
      kind: 'text',
      required: true,
      min_length: 3,
      max_length: 120,
    },
    {
      name: 'body',
      label: 'Body',
      kind: 'rich_text',
      required: true,
      min_length: 1,
    },
    {
      name: 'meta',
      label: 'Meta',
      kind: 'json',
      required: false,
    },
  ],
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-04-21T00:00:00Z',
  updated_at: '2026-04-21T00:00:00Z',
}

const existingEntry: ContentEntryResponse = {
  id: 'entry-1',
  content_type_id: 'type-1',
  content_type_slug: 'articles',
  slug: 'hello-world',
  status: 'draft',
  payload: {
    title: 'Hello World',
    body: '<h2>Hello</h2><p><strong>World</strong></p>',
    meta: {
      featured: true,
    },
  },
  published_at: null,
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-04-21T00:00:00Z',
  updated_at: '2026-04-21T00:00:00Z',
}

describe('content form helpers', () => {
  it('preserves rich-text HTML across form initialization and serialization', () => {
    const state = buildContentEntryFormState(contentType, existingEntry)

    const serialized = serializeContentEntryFormState(contentType, state)

    expect(serialized.slug).toBe('hello-world')
    expect(serialized.payload.body).toBe(existingEntry.payload.body)
    expect(serialized.payload.meta).toEqual({ featured: true })
  })

  it('rejects malformed JSON input before submission', () => {
    const state = buildContentEntryFormState(contentType)
    state.fields.title = 'JSON Example'
    state.fields.body = '<p>Hello</p>'
    state.fields.meta = '{invalid'

    expect(() => serializeContentEntryFormState(contentType, state)).toThrowError(
      new ContentEntryFormError('Meta must contain valid JSON.'),
    )
  })

  it('treats an empty rich-text document as missing required content', () => {
    const state = buildContentEntryFormState(contentType)
    state.fields.title = 'Empty body'
    state.fields.body = '<p></p>'

    expect(() => serializeContentEntryFormState(contentType, state)).toThrowError(
      new ContentEntryFormError('Body is required.'),
    )
    expect(isRichTextEffectivelyEmpty('<p><br></p>')).toBe(true)
  })
})

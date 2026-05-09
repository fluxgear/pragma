import { describe, expect, it } from 'vitest'

import type { ContentEntryResponse, ContentTypeResponse } from '@/api/types'
import {
  ContentEntryFormError,
  buildContentEntryFormState,
  buildContentEntrySeoMetadataFormState,
  isRichTextEffectivelyEmpty,
  serializeContentEntryFormState,
  serializeContentEntrySeoMetadataFormState,
} from '@/features/content/form'

const contentType: ContentTypeResponse = {
  id: 'type-1',
  name: 'Articles',
  slug: 'articles',
  description: 'Article content',
  entry_count: 1,
  can_delete: false,
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
  seo_metadata: {
    title: 'SEO Hello',
    description: 'SEO description',
    canonical_url: '/hello-world',
    robots: 'noindex',
    og_title: 'OG Hello',
    og_description: 'OG description',
    og_image: '/media/og.png',
  },
  version: 3,
  revision_number: 2,
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

  it('deserializes and serializes SEO metadata and expected version fields', () => {
    const state = buildContentEntryFormState(contentType, existingEntry)

    expect(state.seo_metadata).toEqual({
      title: 'SEO Hello',
      description: 'SEO description',
      canonical_url: '/hello-world',
      robots: 'noindex',
      og_title: 'OG Hello',
      og_description: 'OG description',
      og_image: '/media/og.png',
    })
    expect(state.expected_version).toBe(3)

    state.seo_metadata.title = '  Updated SEO  '
    state.seo_metadata.description = ''
    state.seo_metadata.canonical_url = '  /updated  '
    state.seo_metadata.robots = 'index'
    state.seo_metadata.og_image = ''

    const serialized = serializeContentEntryFormState(contentType, state)

    expect(serialized.seo_metadata).toEqual({
      title: 'Updated SEO',
      description: null,
      canonical_url: '/updated',
      robots: 'index',
      og_title: 'OG Hello',
      og_description: 'OG description',
      og_image: null,
    })
    expect(serialized.expected_version).toBe(3)
  })

  it('normalizes empty SEO metadata form fields to backend nulls', () => {
    const state = buildContentEntrySeoMetadataFormState(null)

    expect(state).toEqual({
      title: '',
      description: '',
      canonical_url: '',
      robots: 'index',
      og_title: '',
      og_description: '',
      og_image: '',
    })
    expect(serializeContentEntrySeoMetadataFormState(state)).toEqual({
      title: null,
      description: null,
      canonical_url: null,
      robots: 'index',
      og_title: null,
      og_description: null,
      og_image: null,
    })
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

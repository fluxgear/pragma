import { flushPromises, mount } from '@vue/test-utils'
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { ApiClientError } from '@/api/errors'
import type { ContentEntryResponse, ContentEntrySeoMetadata, ContentTypeResponse } from '@/api/types'

const aiApiMocks = vi.hoisted(() => ({
  generateAiText: vi.fn(),
}))

vi.mock('@/api/ai', () => aiApiMocks)

import ContentEntryForm from '@/components/content/ContentEntryForm.vue'

const contentType: ContentTypeResponse = {
  id: 'content-type-1',
  name: 'Pages',
  slug: 'page',
  description: null,
  entry_count: 0,
  can_delete: true,
  field_definitions: [
    {
      name: 'body',
      label: 'Body',
      kind: 'rich_text',
      required: true,
      min_length: null,
      max_length: null,
    },
  ],
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-05-02T00:00:00Z',
  updated_at: '2026-05-02T00:00:00Z',
}

const defaultSeoMetadata: ContentEntrySeoMetadata = {
  title: null,
  description: null,
  canonical_url: null,
  robots: 'index',
  og_title: null,
  og_description: null,
  og_image: null,
}

const entry: ContentEntryResponse = {
  id: 'entry-1',
  content_type_id: 'content-type-1',
  content_type_slug: 'page',
  slug: 'home',
  status: 'draft',
  payload: { body: '<p>Existing page copy</p>' },
  seo_metadata: defaultSeoMetadata,
  version: 8,
  revision_number: 4,
  published_at: null,
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-05-02T00:00:00Z',
  updated_at: '2026-05-02T00:05:00Z',
}

function generationResponse(text: string) {
  return {
    provider: 'openai_compatible',
    api_mode: 'chat_completions',
    model: 'gpt-5-mini',
    text,
    finish_reason: 'stop',
    usage: null,
  }
}

const originalMatchMedia = window.matchMedia

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
})

afterAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  })
})

describe('ContentEntryForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('associates rich-text field labels with the editable region', async () => {
    const wrapper = mount(ContentEntryForm, {
      props: {
        contentType,
        canPublish: true,
      },
      global: {
        plugins: [[PrimeVue, { theme: { preset: Aura } }]],
      },
    })

    await flushPromises()

    const label = wrapper.get('label[for="entry-field-body"]')
    const editable = wrapper.get('.tiptap')

    expect(label.attributes('id')).toBe('entry-field-body-label')
    expect(editable.attributes('id')).toBe('entry-field-body')
    expect(editable.attributes('aria-labelledby')).toBe('entry-field-body-label')
  })

  it('keeps AI SEO suggestions draft-only until accepted and submitted', async () => {
    aiApiMocks.generateAiText.mockResolvedValue(generationResponse(JSON.stringify({
      title: 'Suggested SEO title',
      description: 'Suggested meta description',
      og_title: 'Suggested social title',
      og_description: 'Suggested social description',
    })))
    const wrapper = mount(ContentEntryForm, {
      props: {
        contentType,
        entry,
        canPublish: true,
      },
      global: {
        plugins: [[PrimeVue, { theme: { preset: Aura } }]],
      },
    })

    await flushPromises()
    await wrapper.get('[data-testid="seo-ai-generate"]').trigger('click')
    await flushPromises()

    expect(aiApiMocks.generateAiText).toHaveBeenCalledWith(expect.objectContaining({
      scope: 'seo',
      instructions: expect.stringContaining('Return only JSON'),
      max_output_tokens: 320,
    }))
    expect(wrapper.get('[data-testid="seo-ai-suggestion"]').text()).toContain('Suggested SEO title')
    expect(wrapper.emitted('submit')).toBeUndefined()

    await wrapper.get('[data-testid="seo-ai-accept"]').trigger('click')
    await wrapper.get('form').trigger('submit.prevent')

    const submitted = wrapper.emitted('submit')?.[0]?.[0]
    expect(submitted).toEqual(expect.objectContaining({
      expected_version: 8,
      seo_metadata: expect.objectContaining({
        title: 'Suggested SEO title',
        description: 'Suggested meta description',
        og_title: 'Suggested social title',
        og_description: 'Suggested social description',
      }),
    }))
  })

  it.each([
    [
      'provider unavailable',
      new ApiClientError(400, 'AI provider is disabled', 'AI_SETTINGS_DISABLED'),
      'Provider unavailable: AI provider is disabled',
    ],
    [
      'permission denied',
      new ApiClientError(403, 'Missing permission: ai.seo_assist', 'PERMISSION_DENIED'),
      'Permission denied: Missing permission: ai.seo_assist',
    ],
  ])('shows %s AI SEO errors without submitting', async (_label, error, expectedMessage) => {
    aiApiMocks.generateAiText.mockRejectedValue(error)
    const wrapper = mount(ContentEntryForm, {
      props: {
        contentType,
        entry,
        canPublish: true,
      },
      global: {
        plugins: [[PrimeVue, { theme: { preset: Aura } }]],
      },
    })

    await flushPromises()
    await wrapper.get('[data-testid="seo-ai-generate"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="seo-ai-error"]').text()).toContain(expectedMessage)
    expect(wrapper.find('[data-testid="seo-ai-suggestion"]').exists()).toBe(false)
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

})

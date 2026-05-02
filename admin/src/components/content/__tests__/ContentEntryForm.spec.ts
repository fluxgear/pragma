import { flushPromises, mount } from '@vue/test-utils'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import type { ContentTypeResponse } from '@/api/types'
import ContentEntryForm from '@/components/content/ContentEntryForm.vue'

const contentType: ContentTypeResponse = {
  id: 'content-type-1',
  name: 'Pages',
  slug: 'page',
  description: null,
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
})

import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import type { ContentFieldDefinition } from '@/api/types'
import ContentModelFieldBuilder from '@/components/content/ContentModelFieldBuilder.vue'

class ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

vi.stubGlobal('ResizeObserver', ResizeObserver)

function mountBuilder(fields: ContentFieldDefinition[]) {
  const wrapper = mount(ContentModelFieldBuilder, {
    props: {
      modelValue: fields,
      'onUpdate:modelValue': (nextFields: ContentFieldDefinition[]) => {
        void wrapper.setProps({ modelValue: nextFields })
      },
    },
    global: {
      plugins: [[PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  return wrapper
}

describe('ContentModelFieldBuilder', () => {
  it('renders current C3 field kinds and emits edits for labels, keys, and kind changes', async () => {
    const wrapper = mountBuilder([
      {
        kind: 'text',
        name: 'title',
        label: 'Title',
        required: true,
        min_length: null,
        max_length: 120,
      },
    ])

    const kindSelect = wrapper.get('[data-testid="field-kind-0"]')
    expect(kindSelect.text()).toContain('Short text')
    expect(kindSelect.text()).toContain('Long text')
    expect(kindSelect.text()).toContain('Rich text')
    expect(kindSelect.text()).toContain('Integer')
    expect(kindSelect.text()).toContain('Number')
    expect(kindSelect.text()).toContain('Boolean')
    expect(kindSelect.text()).toContain('Date')
    expect(kindSelect.text()).toContain('Date and time')
    expect(kindSelect.text()).toContain('JSON')

    await wrapper.get('[data-testid="field-label-0"]').setValue('Headline')
    await wrapper.get('[data-testid="field-name-0"]').setValue('headline')
    await kindSelect.setValue('integer')

    const updates = wrapper.emitted('update:modelValue') as unknown[][]
    const latestFields = updates.at(-1)?.[0] as ContentFieldDefinition[]
    expect(latestFields[0]).toMatchObject({
      kind: 'integer',
      name: 'headline',
      label: 'Headline',
      required: true,
      minimum: null,
      maximum: null,
    })
  })

  it('validates duplicate keys, reserved keys, invalid defaults, and constraint ranges', async () => {
    const wrapper = mountBuilder([
      {
        kind: 'text',
        name: 'title',
        label: 'Title',
        required: true,
        min_length: 10,
        max_length: 3,
      },
      {
        kind: 'integer',
        name: 'title',
        label: 'Views',
        required: false,
        minimum: 100,
        maximum: 1,
        default_value: 1.5,
      },
      {
        kind: 'json',
        name: 'status',
        label: '',
        required: false,
        default_value: '{bad json',
      },
    ])

    await flushPromises()

    expect(wrapper.text()).toContain('Minimum length cannot exceed maximum length.')
    expect(wrapper.text()).toContain('Field key duplicates field 1.')
    expect(wrapper.text()).toContain('Minimum value cannot exceed maximum value.')
    expect(wrapper.text()).toContain('Default must be a whole number.')
    expect(wrapper.text()).toContain('This key is reserved by content entries.')
    expect(wrapper.text()).toContain('Label is required.')
    expect(wrapper.text()).toContain('Default JSON must parse successfully.')

    const validationEvents = wrapper.emitted('validation-change') as unknown[][]
    expect(validationEvents.at(-1)?.[0]).toMatchObject({ valid: false })
  })

  it('adds, reorders, and deletes fields through keyboard-reachable buttons', async () => {
    const wrapper = mountBuilder([
      {
        kind: 'text',
        name: 'title',
        label: 'Title',
        required: true,
        min_length: null,
        max_length: null,
      },
      {
        kind: 'boolean',
        name: 'featured',
        label: 'Featured',
        required: false,
      },
    ])

    await wrapper.get('[data-testid="field-builder-add"]').trigger('click')
    let latestFields = (wrapper.emitted('update:modelValue') as unknown[][]).at(-1)?.[0] as ContentFieldDefinition[]
    expect(latestFields).toHaveLength(3)
    expect(latestFields[2]).toMatchObject({ kind: 'text', name: 'field_3', label: 'New field' })

    await wrapper.setProps({ modelValue: latestFields })
    await wrapper.get('[data-testid="field-move-up-2"]').trigger('click')
    latestFields = (wrapper.emitted('update:modelValue') as unknown[][]).at(-1)?.[0] as ContentFieldDefinition[]
    expect(latestFields.map((field) => field.name)).toEqual(['title', 'field_3', 'featured'])

    await wrapper.setProps({ modelValue: latestFields })
    await wrapper.get('[data-testid="field-delete-1"]').trigger('click')
    latestFields = (wrapper.emitted('update:modelValue') as unknown[][]).at(-1)?.[0] as ContentFieldDefinition[]
    expect(latestFields.map((field) => field.name)).toEqual(['title', 'featured'])
  })
})

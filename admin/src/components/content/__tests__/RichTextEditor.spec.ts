import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import RichTextEditor from '@/components/content/RichTextEditor.vue'

describe('RichTextEditor', () => {
  it('loads initial HTML and exposes accessible editor controls', async () => {
    const wrapper = mount(RichTextEditor, {
      props: {
        modelValue: '<p>Hello</p>',
        inputId: 'entry-field-body',
        ariaLabelledby: 'entry-field-body-label',
      },
      global: {
        plugins: [[PrimeVue, { theme: { preset: Aura } }]],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Hello')

    const editable = wrapper.get('.tiptap')
    expect(editable.attributes('id')).toBe('entry-field-body')
    expect(editable.attributes('role')).toBe('textbox')
    expect(editable.attributes('aria-multiline')).toBe('true')
    expect(editable.attributes('aria-labelledby')).toBe('entry-field-body-label')
    expect(wrapper.get('button[aria-label="Bold"]')).toBeTruthy()
    expect(wrapper.get('button[aria-label="Italic"]')).toBeTruthy()
    expect(wrapper.get('button[aria-label="Undo"]')).toBeTruthy()
    expect(wrapper.get('button[aria-label="Redo"]')).toBeTruthy()
    expect(wrapper.get('button[aria-label="Bold"]').attributes('aria-pressed')).toBe('false')

    await wrapper.setProps({
      modelValue: '<h2>Updated</h2><p>Body</p>',
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Updated')
    expect(wrapper.text()).toContain('Body')
  })
})

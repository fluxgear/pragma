import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import RichTextEditor from '@/components/content/RichTextEditor.vue'

describe('RichTextEditor', () => {
  it('loads initial HTML and reacts to external HTML updates', async () => {
    const wrapper = mount(RichTextEditor, {
      props: {
        modelValue: '<p>Hello</p>',
      },
      global: {
        plugins: [[PrimeVue, { theme: { preset: Aura } }]],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Hello')

    await wrapper.setProps({
      modelValue: '<h2>Updated</h2><p>Body</p>',
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Updated')
    expect(wrapper.text()).toContain('Body')
  })
})

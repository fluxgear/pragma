import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import NotFoundView from '@/views/NotFoundView.vue'

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
      { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
    ],
  })

  await router.push('/missing')
  await router.isReady()

  const wrapper = mount(NotFoundView, {
    global: {
      plugins: [router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()

  return { router, wrapper }
}

describe('NotFoundView', () => {
  it('routes its recovery action through the boot route', async () => {
    const { router, wrapper } = await mountView()

    expect(wrapper.text()).toContain('Back to start')

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('home')
  })
})

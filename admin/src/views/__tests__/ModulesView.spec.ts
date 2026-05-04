import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import ModulesView from '@/views/ModulesView.vue'

const moduleApiMocks = vi.hoisted(() => ({
  listModules: vi.fn(),
  updateModuleState: vi.fn(),
}))

vi.mock('@/api/modules', () => moduleApiMocks)

const modulesPayload = {
  items: [
    {
      module_id: 'search',
      name: 'Search',
      version: '1.0.0',
      order: 10,
      enabled: true,
      loaded: true,
      hooks: ['search.index'],
      error_code: null,
    },
  ],
  total: 1,
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(ModulesView, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper }
}

describe('ModulesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    moduleApiMocks.listModules.mockResolvedValue(modulesPayload)
    moduleApiMocks.updateModuleState.mockResolvedValue({
      ...modulesPayload.items[0],
      enabled: false,
    })
  })

  it('loads modules on mount', async () => {
    const { wrapper } = await mountView()

    expect(moduleApiMocks.listModules).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Search')
    expect(wrapper.text()).toContain('search · v1.0.0')
    expect(wrapper.text()).toContain('Enabled')
  })

  it('updates module state from the actions column', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="module-toggle-state"]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(moduleApiMocks.updateModuleState).toHaveBeenCalledWith('search', { enabled: false })
    expect(moduleApiMocks.listModules).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Search disabled.')
  })

  it('renders module load errors', async () => {
    moduleApiMocks.listModules.mockRejectedValue(new Error('Module API unavailable'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Module API unavailable')
  })
})

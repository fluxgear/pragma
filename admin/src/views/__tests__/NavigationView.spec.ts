import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { ApiClientError } from '@/api/errors'
import NavigationView from '@/views/NavigationView.vue'

const navigationApiMocks = vi.hoisted(() => ({
  getPrimaryNavigationMenu: vi.fn(),
  listNavigationContentOptions: vi.fn(),
  replacePrimaryNavigationMenu: vi.fn(),
}))

vi.mock('@/api/navigation', () => navigationApiMocks)

const contentOptions = {
  items: [
    {
      id: '11111111-1111-4111-8111-111111111111',
      label: 'Draft page',
      content_type_slug: 'page',
      slug: 'draft-page',
      status: 'draft',
      href: '/pages/draft-page',
    },
    {
      id: '22222222-2222-4222-8222-222222222222',
      label: 'About page',
      content_type_slug: 'page',
      slug: 'about',
      status: 'published',
      href: '/pages/about',
    },
  ],
  total: 2,
  limit: 100,
  offset: 0,
}

const loadedMenu = {
  key: 'primary',
  items: [
    {
      id: 'item-1',
      parent_item_id: null,
      position: 1,
      label: 'Docs',
      link_type: 'custom_url',
      enabled: true,
      content_entry_id: null,
      url: 'https://example.com/docs',
      href: 'https://example.com/docs',
      content_type_slug: null,
      entry_slug: null,
      entry_status: null,
      children: [
        {
          id: 'item-1-child',
          parent_item_id: 'item-1',
          position: 1,
          label: 'API',
          link_type: 'custom_url',
          enabled: true,
          content_entry_id: null,
          url: '/docs/api',
          href: '/docs/api',
          content_type_slug: null,
          entry_slug: null,
          entry_status: null,
          children: [],
        },
      ],
    },
    {
      id: 'item-2',
      parent_item_id: null,
      position: 2,
      label: 'Draft page',
      link_type: 'content_entry',
      enabled: true,
      content_entry_id: '11111111-1111-4111-8111-111111111111',
      url: null,
      href: '/pages/draft-page',
      content_type_slug: 'pages',
      entry_slug: 'draft-page',
      entry_status: 'draft',
      children: [],
    },
  ],
  warnings: [
    {
      code: 'NAVIGATION_TARGET_NOT_PUBLISHED',
      detail: 'Internal navigation target is not currently published.',
      item_position: 2,
      item_label: 'Draft page',
      content_entry_id: '11111111-1111-4111-8111-111111111111',
    },
  ],
}

async function mountView() {
  const wrapper = mount(NavigationView, {
    global: {
      plugins: [[PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return wrapper
}

describe('NavigationView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigationApiMocks.getPrimaryNavigationMenu.mockResolvedValue(loadedMenu)
    navigationApiMocks.listNavigationContentOptions.mockResolvedValue(contentOptions)
    navigationApiMocks.replacePrimaryNavigationMenu.mockResolvedValue(loadedMenu)
  })

  it('loads the primary menu with nested copy, picker options, and target warnings', async () => {
    const wrapper = await mountView()

    expect(navigationApiMocks.getPrimaryNavigationMenu).toHaveBeenCalledTimes(1)
    expect(navigationApiMocks.listNavigationContentOptions).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('add child links to build nested menus')
    expect(wrapper.text()).toContain('Docs')
    expect(wrapper.text()).toContain('API')
    expect(wrapper.text()).toContain('Level 2')
    expect(wrapper.text()).toContain('About page')
    expect(wrapper.text()).toContain('Target warnings')
    expect(wrapper.text()).toContain('Internal navigation target is not currently published.')
    expect(wrapper.text()).toContain('Target draft')
  })

  it('renders loading error and empty states', async () => {
    navigationApiMocks.getPrimaryNavigationMenu.mockRejectedValueOnce(new Error('Backend unavailable'))
    const errorWrapper = await mountView()

    expect(errorWrapper.text()).toContain('Backend unavailable')

    navigationApiMocks.getPrimaryNavigationMenu.mockResolvedValueOnce({ key: 'primary', items: [], warnings: [] })
    navigationApiMocks.listNavigationContentOptions.mockResolvedValueOnce(contentOptions)
    await errorWrapper.findAll('button').find((button) => button.text().includes('Refresh'))?.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(errorWrapper.get('[data-testid=navigation-empty-state]').text()).toContain('No primary navigation items yet')
  })

  it('adds internal and custom links, nests child links, reorders, disables, and saves replacement order', async () => {
    navigationApiMocks.getPrimaryNavigationMenu.mockResolvedValueOnce({ key: 'primary', items: [], warnings: [] })
    navigationApiMocks.replacePrimaryNavigationMenu.mockResolvedValueOnce({
      key: 'primary',
      items: [
        {
          id: 'item-3',
          parent_item_id: null,
          position: 1,
          label: 'Docs',
          link_type: 'custom_url',
          enabled: false,
          content_entry_id: null,
          url: '/docs',
          href: '/docs',
          content_type_slug: null,
          entry_slug: null,
          entry_status: null,
          children: [],
        },
        {
          id: 'item-4',
          parent_item_id: null,
          position: 2,
          label: 'About page',
          link_type: 'content_entry',
          enabled: true,
          content_entry_id: '22222222-2222-4222-8222-222222222222',
          url: null,
          href: '/pages/about',
          content_type_slug: 'pages',
          entry_slug: 'about',
          entry_status: 'published',
          children: [],
        },
      ],
      warnings: [],
    })

    const wrapper = await mountView()

    await wrapper.get('[data-testid=navigation-add-internal]').trigger('click')
    await wrapper.get('[data-testid=navigation-label-0]').setValue('About page')
    await wrapper.get('[data-testid=navigation-entry-0]').setValue('22222222-2222-4222-8222-222222222222')
    await wrapper.get('[data-testid=navigation-add-child-custom-0]').trigger('click')
    await wrapper.get('[data-testid=navigation-label-1]').setValue('Team')
    await wrapper.get('[data-testid=navigation-url-1]').setValue('/team')

    await wrapper.get('[data-testid=navigation-add-custom]').trigger('click')
    await wrapper.get('[data-testid=navigation-label-2]').setValue('Docs')
    await wrapper.get('[data-testid=navigation-url-2]').setValue('/docs')
    await wrapper.get('[data-testid=navigation-enabled-2]').setValue(false)
    await wrapper.get('[data-testid=navigation-move-up-2]').trigger('click')

    await wrapper.get('[data-testid=navigation-save]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(navigationApiMocks.replacePrimaryNavigationMenu).toHaveBeenCalledWith({
      items: [
        {
          label: 'Docs',
          link_type: 'custom_url',
          enabled: false,
          children: [],
          url: '/docs',
        },
        {
          label: 'About page',
          link_type: 'content_entry',
          enabled: true,
          children: [
            {
              label: 'Team',
              link_type: 'custom_url',
              enabled: true,
              children: [],
              url: '/team',
            },
          ],
          content_entry_id: '22222222-2222-4222-8222-222222222222',
        },
      ],
    })
    expect(wrapper.text()).toContain('Primary navigation menu saved.')
  })

  it('resets local edits back to the last loaded menu', async () => {
    const wrapper = await mountView()

    await wrapper.get('[data-testid=navigation-label-0]').setValue('Changed docs')
    expect((wrapper.get('[data-testid=navigation-label-0]').element as HTMLInputElement).value).toBe('Changed docs')

    await wrapper.get('[data-testid=navigation-reset]').trigger('click')
    await flushPromises()

    expect((wrapper.get('[data-testid=navigation-label-0]').element as HTMLInputElement).value).toBe('Docs')
  })

  it('displays backend validation errors returned from save', async () => {
    navigationApiMocks.replacePrimaryNavigationMenu.mockRejectedValueOnce(
      new ApiClientError(422, [
        { loc: ['body', 'items', 0, 'url'], msg: 'Custom URLs must be relative paths or http(s) URLs' },
      ] as unknown as string),
    )

    const wrapper = await mountView()

    await wrapper.get('[data-testid=navigation-save]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('body.items.0.url: Custom URLs must be relative paths or http(s) URLs')
  })
})

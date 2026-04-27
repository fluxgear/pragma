import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import type {
  ContentEntryResponse,
  ContentTypeResponse,
  RealtimeEventEnvelope,
} from '@/api/types'
import ContentEntryForm from '@/components/content/ContentEntryForm.vue'
import ContentEntriesView from '@/views/ContentEntriesView.vue'

const contentApiMocks = vi.hoisted(() => ({
  createContentEntry: vi.fn(),
  listContentEntries: vi.fn(),
  listContentTypes: vi.fn(),
  updateContentEntry: vi.fn(),
}))

const realtimeStoreMocks = vi.hoisted(() => {
  let eventHandler: ((event: RealtimeEventEnvelope) => void) | null = null
  let resyncHandler: (() => void) | null = null

  return {
    subscribe: vi.fn((handler: (event: RealtimeEventEnvelope) => void) => {
      eventHandler = handler
      return () => {
        if (eventHandler === handler) {
          eventHandler = null
        }
      }
    }),
    subscribeResync: vi.fn((handler: () => void) => {
      resyncHandler = handler
      return () => {
        if (resyncHandler === handler) {
          resyncHandler = null
        }
      }
    }),
    emitEvent(event: RealtimeEventEnvelope) {
      eventHandler?.(event)
    },
    emitResync() {
      resyncHandler?.()
    },
    reset() {
      eventHandler = null
      resyncHandler = null
      this.subscribe.mockClear()
      this.subscribeResync.mockClear()
    },
  }
})

vi.mock('@/api/content', () => contentApiMocks)
vi.mock('@/stores/realtime', () => ({
  useRealtimeStore: () => realtimeStoreMocks,
}))

if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

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
    body: '<p>Hello</p>',
  },
  published_at: null,
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-04-21T00:00:00Z',
  updated_at: '2026-04-21T00:00:00Z',
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/app/content', name: 'content', component: ContentEntriesView },
    ],
  })
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createTestRouter()
  await router.push('/app/content')
  await router.isReady()

  const wrapper = mount(ContentEntriesView, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper }
}

describe('ContentEntriesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    realtimeStoreMocks.reset()
    contentApiMocks.listContentTypes.mockResolvedValue({
      items: [contentType],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries.mockResolvedValue({
      items: [existingEntry],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.createContentEntry.mockResolvedValue(existingEntry)
    contentApiMocks.updateContentEntry.mockResolvedValue(existingEntry)
  })

  it('loads content types and existing entries into the workspace', async () => {
    const { wrapper } = await mountView()

    expect(contentApiMocks.listContentTypes).toHaveBeenCalledTimes(1)
    expect(contentApiMocks.listContentEntries).toHaveBeenCalledWith({
      content_type_id: 'type-1',
    })
    expect(wrapper.text()).toContain('Content entries')
    expect(wrapper.text()).toContain('Articles')
    expect(wrapper.text()).toContain('Hello World')
  })

  it('creates a new entry from the dialog form payload and reloads the list', async () => {
    const { wrapper } = await mountView()

    const newEntryButton = wrapper.findAll('button').find((button) => button.text().includes('New entry'))
    if (!newEntryButton) {
      throw new Error('New entry button not found')
    }

    await newEntryButton.trigger('click')
    await flushPromises()

    const form = wrapper.getComponent(ContentEntryForm)
    form.vm.$emit('submit', {
      slug: null,
      status: 'published',
      payload: {
        title: 'Created from dialog',
        body: '<p>Created</p>',
      },
    })
    await flushPromises()

    expect(contentApiMocks.createContentEntry).toHaveBeenCalledWith({
      content_type_id: 'type-1',
      slug: null,
      status: 'published',
      payload: {
        title: 'Created from dialog',
        body: '<p>Created</p>',
      },
    })
    expect(contentApiMocks.listContentEntries).toHaveBeenCalledTimes(2)
  })

  it('updates an existing entry from the dialog form payload', async () => {
    const { wrapper } = await mountView()

    const editButton = wrapper.findAll('button').find((button) => button.text().includes('Edit'))
    if (!editButton) {
      throw new Error('Edit button not found')
    }

    await editButton.trigger('click')
    await flushPromises()

    const form = wrapper.getComponent(ContentEntryForm)
    form.vm.$emit('submit', {
      slug: 'hello-world',
      status: 'archived',
      payload: {
        title: 'Hello World',
        body: '<blockquote><p>Archived</p></blockquote>',
      },
    })
    await flushPromises()

    expect(contentApiMocks.updateContentEntry).toHaveBeenCalledWith('entry-1', {
      slug: 'hello-world',
      status: 'archived',
      payload: {
        title: 'Hello World',
        body: '<blockquote><p>Archived</p></blockquote>',
      },
    })
  })

  it('reloads entries when realtime event matches selected content type', async () => {
    await mountView()

    realtimeStoreMocks.emitEvent({
      version: 1,
      id: 'evt-1',
      type: 'content.entry.updated',
      resource: 'content.entry',
      action: 'updated',
      resource_id: 'entry-1',
      occurred_at: '2026-04-21T00:00:00Z',
      actor_id: 'user-1',
      data: {
        content_type_id: 'type-1',
      },
    })
    await flushPromises()

    expect(contentApiMocks.listContentEntries).toHaveBeenCalledTimes(2)
  })

  it('ignores realtime entry events for other content types', async () => {
    await mountView()

    realtimeStoreMocks.emitEvent({
      version: 1,
      id: 'evt-2',
      type: 'content.entry.updated',
      resource: 'content.entry',
      action: 'updated',
      resource_id: 'entry-1',
      occurred_at: '2026-04-21T00:00:00Z',
      actor_id: 'user-1',
      data: {
        content_type_id: 'type-999',
      },
    })
    await flushPromises()

    expect(contentApiMocks.listContentEntries).toHaveBeenCalledTimes(1)
  })

  it('refreshes content types and entries when realtime resync is requested', async () => {
    await mountView()

    realtimeStoreMocks.emitResync()
    await flushPromises()

    expect(contentApiMocks.listContentTypes).toHaveBeenCalledTimes(2)
    expect(contentApiMocks.listContentEntries).toHaveBeenCalledTimes(2)
  })
})

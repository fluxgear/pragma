import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiClientError } from '@/api/errors'
import type {
  BlockDocument,
  ContentEntryResponse,
  ContentEntryRevisionResponse,
  ContentEntrySeoMetadata,
  ContentTypeResponse,
  RealtimeEventEnvelope,
} from '@/api/types'
import BlockEditorShell from '@/components/content/blocks/BlockEditorShell.vue'
import ContentEntryForm from '@/components/content/ContentEntryForm.vue'
import { useAuthStore } from '@/stores/auth'
import ContentEntriesView from '@/views/ContentEntriesView.vue'

const contentApiMocks = vi.hoisted(() => ({
  cancelContentEntrySchedule: vi.fn(),
  createContentEntry: vi.fn(),
  createContentEntryPreview: vi.fn(),
  deleteContentEntryAutosave: vi.fn(),
  getContentEntryAutosave: vi.fn(),
  getContentEntrySchedule: vi.fn(),
  listContentEntries: vi.fn(),
  listContentEntryActivity: vi.fn(),
  listContentEntryRevisions: vi.fn(),
  listContentTypes: vi.fn(),
  publishContentEntry: vi.fn(),
  restoreContentEntryRevision: vi.fn(),
  saveContentEntryAutosave: vi.fn(),
  setContentEntrySchedule: vi.fn(),
  unpublishContentEntry: vi.fn(),
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
  ],
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-04-21T00:00:00Z',
  updated_at: '2026-04-21T00:00:00Z',
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
  seo_metadata: defaultSeoMetadata,
  version: 4,
  revision_number: 3,
  published_at: null,
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-04-21T00:00:00Z',
  updated_at: '2026-04-21T00:00:00Z',
}

const blockDocument: BlockDocument = {
  version: 1,
  root: {
    type: 'section',
    props: {},
    settings: {},
    children: [
      {
        type: 'container',
        props: {},
        settings: {},
        children: [
          { type: 'heading', props: { text: 'Block page', level: 2 }, settings: {}, children: [] },
        ],
      },
    ],
  },
}

const blockContentType: ContentTypeResponse = {
  ...contentType,
  id: 'type-block',
  name: 'Pages',
  slug: 'pages',
  description: 'Composable pages',
  field_definitions: [
    {
      name: 'title',
      label: 'Title',
      kind: 'text',
      required: true,
      min_length: 1,
      max_length: 120,
    },
    {
      name: 'body',
      label: 'Body',
      kind: 'block_document',
      required: false,
      help_text: 'Block page body.',
    },
  ],
}

const blockEntry: ContentEntryResponse = {
  ...existingEntry,
  id: 'entry-block',
  content_type_id: 'type-block',
  content_type_slug: 'pages',
  slug: 'home',
  payload: {
    title: 'Home',
    body: blockDocument,
  },
}

const revisionRecord: ContentEntryRevisionResponse = {
  id: 'revision-3',
  entry_id: 'entry-1',
  revision_number: 3,
  action: 'update',
  slug: 'hello-world',
  status: 'draft',
  payload: existingEntry.payload,
  seo_metadata: defaultSeoMetadata,
  published_at: null,
  created_by_user_id: null,
  created_at: '2026-04-21T00:05:00Z',
  restore_source_revision_id: null,
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/app/content', name: 'content', component: ContentEntriesView },
      { path: '/app/content-models', name: 'content-models', component: { template: '<div>Content models</div>' } },
    ],
  })
}

async function mountView(permissions = [
  'content.entries.read',
  'content.entries.write',
  'content.entries.publish',
  'content.types.read',
], initialRoute = '/app/content') {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = 'token-123'
  authStore.user = {
    id: 'user-1',
    email: 'author@example.com',
    username: 'author',
    full_name: null,
    is_active: true,
    is_superuser: false,
    roles: ['author'],
    permissions,
    force_password_change: false,
  }

  const router = createTestRouter()
  await router.push(initialRoute)
  await router.isReady()

  const wrapper = mount(ContentEntriesView, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper, router }
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
    contentApiMocks.listContentEntryRevisions.mockResolvedValue({ items: [revisionRecord] })
    contentApiMocks.createContentEntry.mockResolvedValue(existingEntry)
    contentApiMocks.updateContentEntry.mockResolvedValue(existingEntry)
    contentApiMocks.publishContentEntry.mockResolvedValue({ ...existingEntry, status: 'published', version: 5, revision_number: 4 })
    contentApiMocks.unpublishContentEntry.mockResolvedValue({ ...existingEntry, status: 'draft', version: 6, revision_number: 5 })
    contentApiMocks.restoreContentEntryRevision.mockResolvedValue({ ...existingEntry, version: 7, revision_number: 6 })
    contentApiMocks.createContentEntryPreview.mockResolvedValue({
      entry_id: 'entry-1',
      token: 'preview-token',
      preview_url: '/preview/content/preview-token',
      expires_at: '2026-04-21T00:15:00Z',
    })
    contentApiMocks.getContentEntryAutosave.mockRejectedValue(new ApiClientError(404, 'Autosave not found', 'CONTENT_ENTRY_AUTOSAVE_NOT_FOUND'))
    contentApiMocks.getContentEntrySchedule.mockResolvedValue({ entry_id: 'entry-1', publish: null, unpublish: null })
    contentApiMocks.listContentEntryActivity.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 })
    contentApiMocks.saveContentEntryAutosave.mockResolvedValue({
      entry_id: 'entry-1',
      user_id: 'user-1',
      base_version: 4,
      current_version: 4,
      is_stale: false,
      slug: 'hello-world',
      payload: existingEntry.payload,
      seo_metadata: existingEntry.seo_metadata,
      updated_at: '2026-04-21T00:05:00Z',
    })
    contentApiMocks.deleteContentEntryAutosave.mockResolvedValue(undefined)
    contentApiMocks.setContentEntrySchedule.mockResolvedValue({
      entry_id: 'entry-1',
      publish: {
        id: 'schedule-1',
        entry_id: 'entry-1',
        action: 'publish',
        run_at: '2026-04-22T09:00:00Z',
        requested_entry_version: 4,
        requested_by_user_id: 'user-1',
        state: 'pending',
        created_at: '2026-04-21T00:00:00Z',
        updated_at: '2026-04-21T00:00:00Z',
        executed_at: null,
        cancelled_at: null,
        failure_code: null,
        failure_detail: null,
      },
      unpublish: null,
    })
    contentApiMocks.cancelContentEntrySchedule.mockResolvedValue({ entry_id: 'entry-1', publish: null, unpublish: null })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads content types and existing entries into the workspace', async () => {
    const { wrapper } = await mountView()

    expect(contentApiMocks.listContentTypes).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
      order_by: 'updated_at',
    })
    expect(contentApiMocks.listContentEntries).toHaveBeenCalledWith({
      content_type_id: 'type-1',
      limit: 50,
      offset: 0,
      order_by: 'updated_at',
    })
    expect(wrapper.text()).toContain('Content entries')
    expect(wrapper.text()).toContain('Articles')
    expect(wrapper.text()).toContain('Hello World')
  })

  it('links to content models when no models exist and the user can read models', async () => {
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    const { wrapper, router } = await mountView(['content.entries.read', 'content.types.read'])

    expect(wrapper.text()).toContain('No content models exist yet')
    expect(wrapper.text()).toContain('Create a content model before authoring entries')
    expect(wrapper.text()).not.toContain('content API first')
    expect(contentApiMocks.listContentEntries).not.toHaveBeenCalled()

    await wrapper.get('[data-testid="open-content-models"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/app/content-models')
  })

  it('shows no-permission guidance when no models exist and the user cannot read models', async () => {
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    const { wrapper } = await mountView(['content.entries.read'])

    expect(wrapper.text()).toContain('Content entries need a content model')
    expect(wrapper.text()).toContain('Ask an administrator with content model access')
    expect(wrapper.text()).not.toContain('content API first')
    expect(wrapper.find('[data-testid="open-content-models"]').exists()).toBe(false)
  })

  it('auto-selects the contentTypeId query parameter after content types load', async () => {
    const secondContentType: ContentTypeResponse = {
      ...contentType,
      id: 'type-2',
      name: 'Pages',
      slug: 'pages',
      description: 'Page content',
      entry_count: 0,
      can_delete: true,
    }
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [contentType, secondContentType],
      total: 2,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    const { wrapper } = await mountView(undefined, '/app/content?contentTypeId=type-2')

    expect(contentApiMocks.listContentEntries).toHaveBeenCalledWith({
      content_type_id: 'type-2',
      limit: 50,
      offset: 0,
      order_by: 'updated_at',
    })
    expect(wrapper.text()).toContain('Pages')
    expect(wrapper.text()).toContain('Page content')
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
      seo_metadata: { ...defaultSeoMetadata, title: 'Created SEO' },
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
      seo_metadata: { ...defaultSeoMetadata, title: 'Created SEO' },
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
      seo_metadata: { ...defaultSeoMetadata, description: 'Archived description' },
      expected_version: 4,
    })
    await flushPromises()

    expect(contentApiMocks.updateContentEntry).toHaveBeenCalledWith('entry-1', {
      slug: 'hello-world',
      status: 'archived',
      payload: {
        title: 'Hello World',
        body: '<blockquote><p>Archived</p></blockquote>',
      },
      seo_metadata: { ...defaultSeoMetadata, description: 'Archived description' },
      expected_version: 4,
    })
  })

  it('opens the block editor shell for block-document content types and stores route state', async () => {
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [blockContentType],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries.mockResolvedValueOnce({
      items: [blockEntry],
      total: 1,
      limit: 50,
      offset: 0,
    })

    const { wrapper, router } = await mountView()

    await wrapper.get('[data-testid="entry-edit"]').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(ContentEntryForm).exists()).toBe(false)
    expect(wrapper.getComponent(BlockEditorShell).text()).toContain('Editing home')
    expect(wrapper.text()).toContain('Draft suggestion assistant')
    expect(wrapper.text()).toContain('backend /ai/generate editor scope')
    expect(router.currentRoute.value.query.blockEditor).toBe('entry-block')
  })

  it('opens a new-entry block editor shell without saving for block-document content types', async () => {
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [blockContentType],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    const { wrapper, router } = await mountView()

    const newEntryButton = wrapper.findAll('button').find((button) => button.text().includes('New entry'))
    if (!newEntryButton) {
      throw new Error('New entry button not found')
    }

    await newEntryButton.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(ContentEntryForm).exists()).toBe(false)
    expect(wrapper.getComponent(BlockEditorShell).text()).toContain('New Pages block entry')
    expect(wrapper.text()).toContain('No block document content yet')
    expect(router.currentRoute.value.query.blockEditor).toBe('new')
    expect(contentApiMocks.createContentEntry).not.toHaveBeenCalled()
  })

  it('guards block editor close when editable draft changes may be unsaved', async () => {
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [blockContentType],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)

    const { wrapper, router } = await mountView()

    const newEntryButton = wrapper.findAll('button').find((button) => button.text().includes('New entry'))
    if (!newEntryButton) {
      throw new Error('New entry button not found')
    }

    await newEntryButton.trigger('click')
    await flushPromises()

    wrapper.getComponent(BlockEditorShell).vm.$emit('close')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalledWith('You have unsaved content changes. Leave without saving?')
    expect(wrapper.findComponent(BlockEditorShell).exists()).toBe(true)
    expect(router.currentRoute.value.query.blockEditor).toBe('new')

    wrapper.getComponent(BlockEditorShell).vm.$emit('close')
    await flushPromises()

    expect(wrapper.findComponent(BlockEditorShell).exists()).toBe(false)
    expect(router.currentRoute.value.query.blockEditor).toBeUndefined()
  })

  it('creates a draft block-document entry, updates route state, and reloads the saved document', async () => {
    const createdEntry: ContentEntryResponse = {
      ...blockEntry,
      id: 'entry-created',
      slug: 'created-page',
      payload: {
        title: 'Untitled Pages',
        body: {
          version: 1,
          root: {
            type: 'section',
            props: {},
            settings: {},
            children: [
              { type: 'heading', props: { text: 'Saved page', level: 2 }, settings: {}, children: [] },
            ],
          },
        },
      },
    }
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [blockContentType],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [createdEntry],
        total: 1,
        limit: 50,
        offset: 0,
      })
    contentApiMocks.createContentEntry.mockResolvedValueOnce(createdEntry)

    const { wrapper, router } = await mountView()

    const newEntryButton = wrapper.findAll('button').find((button) => button.text().includes('New entry'))
    if (!newEntryButton) {
      throw new Error('New entry button not found')
    }

    await newEntryButton.trigger('click')
    await flushPromises()

    const shell = wrapper.getComponent(BlockEditorShell)
    shell.vm.$emit('save', createdEntry.payload.body as BlockDocument)
    await flushPromises()
    await flushPromises()

    expect(contentApiMocks.createContentEntry).toHaveBeenCalledWith({
      content_type_id: 'type-block',
      slug: null,
      status: 'draft',
      payload: {
        title: 'Untitled Pages',
        body: createdEntry.payload.body,
      },
    })
    expect(contentApiMocks.listContentEntries).toHaveBeenCalledTimes(2)
    expect(router.currentRoute.value.query.blockEditor).toBe('entry-created')
    expect(wrapper.getComponent(BlockEditorShell).text()).toContain('Editing created-page')
    expect(wrapper.getComponent(BlockEditorShell).text()).toContain('Saved page')
  })

  it('updates an existing block-document entry and reloads modified block payload', async () => {
    const updatedDocument: BlockDocument = {
      version: 1,
      root: {
        type: 'section',
        props: {},
        settings: {},
        children: [
          { type: 'heading', props: { text: 'Reloaded heading', level: 2 }, settings: {}, children: [] },
        ],
      },
    }
    const updatedEntry: ContentEntryResponse = {
      ...blockEntry,
      payload: {
        ...blockEntry.payload,
        body: updatedDocument,
      },
    }
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [blockContentType],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries
      .mockResolvedValueOnce({
        items: [blockEntry],
        total: 1,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [updatedEntry],
        total: 1,
        limit: 50,
        offset: 0,
      })
    contentApiMocks.updateContentEntry.mockResolvedValueOnce(updatedEntry)

    const { wrapper, router } = await mountView()

    await wrapper.get('[data-testid="entry-edit"]').trigger('click')
    await flushPromises()

    wrapper.getComponent(BlockEditorShell).vm.$emit('save', updatedDocument)
    await flushPromises()
    await flushPromises()

    expect(contentApiMocks.updateContentEntry).toHaveBeenCalledWith('entry-block', {
      slug: 'home',
      status: 'draft',
      payload: {
        title: 'Home',
        body: updatedDocument,
      },
      seo_metadata: defaultSeoMetadata,
      expected_version: 4,
    })
    expect(contentApiMocks.listContentEntries).toHaveBeenCalledTimes(2)
    expect(router.currentRoute.value.query.blockEditor).toBe('entry-block')
    expect(wrapper.getComponent(BlockEditorShell).text()).toContain('Reloaded heading')
  })

  it('opens existing block documents read-only when the user cannot write and blocks save', async () => {
    contentApiMocks.listContentTypes.mockResolvedValueOnce({
      items: [blockContentType],
      total: 1,
      limit: 50,
      offset: 0,
    })
    contentApiMocks.listContentEntries.mockResolvedValueOnce({
      items: [blockEntry],
      total: 1,
      limit: 50,
      offset: 0,
    })

    const { wrapper } = await mountView(['content.entries.read', 'content.types.read'])

    await wrapper.get('[data-testid="entry-edit"]').trigger('click')
    await flushPromises()

    const shell = wrapper.getComponent(BlockEditorShell)
    expect(shell.props('readOnly')).toBe(true)
    expect(shell.text()).toContain('Read-only preview')
    expect(shell.get('[data-testid="block-editor-save"]').attributes('disabled')).toBeDefined()

    shell.vm.$emit('save', blockDocument)
    await flushPromises()

    expect(contentApiMocks.updateContentEntry).not.toHaveBeenCalled()
    expect(shell.text()).toContain('You do not have permission to save this block document')
  })

  it('coalesces matching realtime entry event bursts into one delayed reload', async () => {
    await mountView()

    vi.useFakeTimers()

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
    realtimeStoreMocks.emitEvent({
      version: 1,
      id: 'evt-2',
      type: 'content.entry.created',
      resource: 'content.entry',
      action: 'created',
      resource_id: 'entry-2',
      occurred_at: '2026-04-21T00:00:01Z',
      actor_id: 'user-1',
      data: {
        content_type_id: 'type-1',
      },
    })
    realtimeStoreMocks.emitEvent({
      version: 1,
      id: 'evt-3',
      type: 'content.entry.deleted',
      resource: 'content.entry',
      action: 'deleted',
      resource_id: 'entry-3',
      occurred_at: '2026-04-21T00:00:02Z',
      actor_id: 'user-1',
      data: {
        content_type_id: 'type-1',
      },
    })
    await flushPromises()

    expect(contentApiMocks.listContentEntries).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(100)
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

  it('navigates content type and entry pages with backend pagination parameters', async () => {
    const secondContentType: ContentTypeResponse = {
      ...contentType,
      id: 'type-2',
      name: 'Pages',
      slug: 'pages',
    }
    contentApiMocks.listContentTypes
      .mockResolvedValueOnce({
        items: [contentType],
        total: 75,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [secondContentType],
        total: 75,
        limit: 50,
        offset: 50,
      })
    contentApiMocks.listContentEntries
      .mockResolvedValueOnce({
        items: [existingEntry],
        total: 75,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 75,
        limit: 50,
        offset: 50,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      })

    const { wrapper } = await mountView()

    expect(wrapper.get('[data-testid="content-types-pagination-summary"]').text()).toContain('1-1 of 75')
    expect(wrapper.get('[data-testid="entries-pagination-summary"]').text()).toContain('1-1 of 75')

    await wrapper.get('[data-testid="entries-next"]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.listContentEntries).toHaveBeenCalledWith({
      content_type_id: 'type-1',
      limit: 50,
      offset: 50,
      order_by: 'updated_at',
    })

    await wrapper.get('[data-testid="content-types-next"]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.listContentTypes).toHaveBeenLastCalledWith({
      limit: 50,
      offset: 50,
      order_by: 'updated_at',
    })
  })


  it('creates and opens preview URLs from the workflow panel', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="workflow-preview"]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.createContentEntryPreview).toHaveBeenCalledWith('entry-1')
    expect(openSpy).toHaveBeenCalledWith('/preview/content/preview-token', '_blank', 'noopener,noreferrer')
    expect(wrapper.get('[data-testid="workflow-preview-link"]').attributes('href')).toBe('/preview/content/preview-token')
  })

  it('publishes and unpublishes with the current expected_version', async () => {
    const publishedEntry: ContentEntryResponse = {
      ...existingEntry,
      status: 'published',
      published_at: '2026-04-21T00:10:00Z',
    }
    contentApiMocks.listContentEntries.mockResolvedValueOnce({
      items: [existingEntry],
      total: 1,
      limit: 50,
      offset: 0,
    }).mockResolvedValueOnce({
      items: [publishedEntry],
      total: 1,
      limit: 50,
      offset: 0,
    })

    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="workflow-publish"]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.publishContentEntry).toHaveBeenCalledWith('entry-1', { expected_version: 4 })

    await wrapper.get('[data-testid="workflow-unpublish"]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.unpublishContentEntry).toHaveBeenCalledWith('entry-1', { expected_version: 4 })
  })

  it('restores a revision only after confirmation and includes expected_version', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.get('[data-testid="revision-restore"]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.restoreContentEntryRevision).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="revision-restore-confirm"]').text()).toContain('expected_version 4')

    await wrapper.get('[data-testid="revision-restore-confirm-button"]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.restoreContentEntryRevision).toHaveBeenCalledWith('entry-1', 'revision-3', { expected_version: 4 })
  })

  it('surfaces version conflict and permission denial workflow errors', async () => {
    contentApiMocks.publishContentEntry.mockRejectedValueOnce(
      new ApiClientError(409, 'Entry has changed.', 'CONTENT_ENTRY_VERSION_CONFLICT'),
    )
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="workflow-publish"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="workflow-error"]').text()).toContain('Version conflict')

    contentApiMocks.createContentEntryPreview.mockRejectedValueOnce(
      new ApiClientError(403, 'Missing permission: content.entries.write', 'PERMISSION_DENIED'),
    )
    await wrapper.get('[data-testid="workflow-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="workflow-error"]').text()).toContain('Permission denied')
  })

  it('exposes autosave, scheduling, and activity workflow controls', async () => {
    contentApiMocks.listContentEntryActivity.mockResolvedValue({
      items: [
        {
          id: 'activity-1',
          entry_id: 'entry-1',
          content_type_id: 'type-1',
          entry_slug: 'hello-world',
          entry_version: 4,
          action: 'autosave',
          actor_user_id: 'user-1',
          details: {},
          created_at: '2026-04-21T00:05:00Z',
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    })

    const { wrapper } = await mountView()

    expect(contentApiMocks.getContentEntryAutosave).toHaveBeenCalledWith('entry-1')
    expect(contentApiMocks.getContentEntrySchedule).toHaveBeenCalledWith('entry-1')
    expect(contentApiMocks.listContentEntryActivity).toHaveBeenCalledWith('entry-1')
    expect(wrapper.text()).toContain('Autosave safety copy')
    expect(wrapper.text()).toContain('autosave')

    await wrapper.get('[data-testid=content-entry-autosave-save]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.saveContentEntryAutosave).toHaveBeenCalledWith('entry-1', {
      base_version: 4,
      slug: 'hello-world',
      payload: existingEntry.payload,
      seo_metadata: existingEntry.seo_metadata,
    })
    expect(wrapper.text()).toContain('Autosave safety copy saved.')

    await wrapper.get('[data-testid=content-entry-schedule-publish-at]').setValue('2026-04-22T09:00')
    await wrapper.get('[data-testid=content-entry-schedule-save]').trigger('click')
    await flushPromises()

    expect(contentApiMocks.setContentEntrySchedule).toHaveBeenCalledWith('entry-1', {
      expected_version: 4,
      publish_at: expect.any(String),
      unpublish_at: null,
    })
    expect(wrapper.text()).toContain('Schedule saved.')
  })

  it('disables create and edit controls for read-only users', async () => {
    const { wrapper } = await mountView(['content.entries.read'])

    const newEntryButton = wrapper.findAll('button').find((button) => button.text().includes('New entry'))
    if (!newEntryButton) {
      throw new Error('New entry button not found')
    }

    const editButton = wrapper.get('[data-testid="entry-edit"]')

    expect(newEntryButton.attributes('disabled')).toBeDefined()
    expect(editButton.attributes('disabled')).toBeDefined()
    await newEntryButton.trigger('click')
    await editButton.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(ContentEntryForm).exists()).toBe(false)
    expect(contentApiMocks.createContentEntry).not.toHaveBeenCalled()
    expect(contentApiMocks.updateContentEntry).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('read-only access')
  })

  it('prevents publish submissions for writers without publish permission', async () => {
    const { wrapper } = await mountView(['content.entries.read', 'content.entries.write'])

    const newEntryButton = wrapper.findAll('button').find((button) => button.text().includes('New entry'))
    if (!newEntryButton) {
      throw new Error('New entry button not found')
    }

    await newEntryButton.trigger('click')
    await flushPromises()

    const form = wrapper.getComponent(ContentEntryForm)
    expect(form.props('canPublish')).toBe(false)
    form.vm.$emit('submit', {
      slug: null,
      status: 'published',
      payload: {
        title: 'Blocked publish',
        body: '<p>Blocked</p>',
      },
      seo_metadata: defaultSeoMetadata,
    })
    await flushPromises()

    expect(contentApiMocks.createContentEntry).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('content.entries.publish permission')
  })

  it('disables editing published entries for writers without publish permission', async () => {
    contentApiMocks.listContentEntries.mockResolvedValue({
      items: [{ ...existingEntry, status: 'published' }],
      total: 1,
      limit: 50,
      offset: 0,
    })

    const { wrapper } = await mountView(['content.entries.read', 'content.entries.write'])

    const editButton = wrapper.get('[data-testid="entry-edit"]')

    expect(editButton.attributes('disabled')).toBeDefined()
    await editButton.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(ContentEntryForm).exists()).toBe(false)
    expect(contentApiMocks.updateContentEntry).not.toHaveBeenCalled()
  })
})

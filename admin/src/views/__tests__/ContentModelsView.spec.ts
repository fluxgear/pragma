import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiClientError } from '@/api/errors'
import type { ContentTypeResponse, UserResponse } from '@/api/types'
import ContentModelForm from '@/components/content/ContentModelForm.vue'
import { useAuthStore } from '@/stores/auth'
import ContentModelsView from '@/views/ContentModelsView.vue'

class ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

vi.stubGlobal('ResizeObserver', ResizeObserver)

const contentApiMocks = vi.hoisted(() => ({
  createContentType: vi.fn(),
  deleteContentType: vi.fn(),
  listContentTypes: vi.fn(),
  updateContentType: vi.fn(),
}))

vi.mock('@/api/content', () => contentApiMocks)

const baseModel: ContentTypeResponse = {
  id: 'type-1',
  name: 'Articles',
  slug: 'articles',
  description: 'Editorial articles',
  field_definitions: [
    {
      kind: 'text',
      name: 'title',
      label: 'Title',
      required: true,
      min_length: 3,
      max_length: 120,
      help_text: 'Reader-facing headline',
    },
    {
      kind: 'rich_text',
      name: 'body',
      label: 'Body',
      required: true,
      min_length: 1,
      max_length: null,
    },
  ],
  entry_count: 3,
  can_delete: false,
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-05-01T00:00:00Z',
  updated_at: '2026-05-02T12:30:00Z',
}

const deletableModel: ContentTypeResponse = {
  ...baseModel,
  id: 'type-2',
  name: 'Landing pages',
  slug: 'landing-pages',
  description: null,
  entry_count: 0,
  can_delete: true,
}

const baseUser: UserResponse = {
  id: 'user-1',
  email: 'admin@example.com',
  username: 'admin',
  full_name: null,
  is_active: true,
  is_superuser: false,
  roles: ['administrator'],
  assigned_permissions: ['content.types.read', 'content.types.manage'],
  effective_permissions: ['content.types.read', 'content.types.manage'],
  has_all_permissions: false,
  permission_source: 'roles',
  permissions: ['content.types.read', 'content.types.manage'],
  force_password_change: false,
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/app/content-models', name: 'content-models', component: ContentModelsView },
      { path: '/app/content', name: 'content', component: { template: '<div>Content entries</div>' } },
    ],
  })
}

async function mountView(permissions = ['content.types.read', 'content.types.manage']) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = 'token-123'
  authStore.user = {
    ...baseUser,
    assigned_permissions: permissions,
    effective_permissions: permissions,
    permissions,
  }

  const router = createTestRouter()
  await router.push('/app/content-models')
  await router.isReady()

  const wrapper = mount(ContentModelsView, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper, router }
}

describe('ContentModelsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    contentApiMocks.listContentTypes.mockResolvedValue({
      items: [baseModel, deletableModel],
      total: 2,
      limit: 100,
      offset: 0,
    })
    contentApiMocks.createContentType.mockResolvedValue(deletableModel)
    contentApiMocks.updateContentType.mockResolvedValue(baseModel)
    contentApiMocks.deleteContentType.mockResolvedValue(undefined)
  })

  it('loads and lists content models with field, entry, delete, and updated metadata', async () => {
    const { wrapper } = await mountView()

    expect(contentApiMocks.listContentTypes).toHaveBeenCalledWith({
      limit: 100,
      offset: 0,
      order_by: 'updated_at',
    })
    expect(wrapper.text()).toContain('Articles')
    expect(wrapper.text()).toContain('Editorial articles')
    expect(wrapper.text()).toContain('articles')
    expect(wrapper.text()).toContain('Fields')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('Entries')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('3 entries in use')
    expect(wrapper.text()).toContain('Delete available')
    expect(wrapper.text()).toContain('Title · text')
  })

  it('shows loading error and empty states', async () => {
    contentApiMocks.listContentTypes.mockRejectedValueOnce(new Error('Network unavailable'))
    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Network unavailable')

    contentApiMocks.listContentTypes.mockResolvedValueOnce({ items: [], total: 0, limit: 100, offset: 0 })
    await wrapper.findAll('button').find((button) => button.text().includes('Refresh'))?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('No content models yet')
  })

  it('creates a model through createContentType, refreshes, and closes the form', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="create-model"]').trigger('click')
    await flushPromises()

    wrapper.getComponent(ContentModelForm).vm.$emit('submit', {
      name: 'Pages',
      slug: 'pages',
      description: null,
      field_definitions: [
        {
          kind: 'text',
          name: 'title',
          label: 'Title',
          required: true,
          min_length: null,
          max_length: 160,
        },
      ],
    })
    await flushPromises()
    await flushPromises()

    expect(contentApiMocks.createContentType).toHaveBeenCalledWith({
      name: 'Pages',
      slug: 'pages',
      description: null,
      field_definitions: [
        {
          kind: 'text',
          name: 'title',
          label: 'Title',
          required: true,
          min_length: null,
          max_length: 160,
        },
      ],
    })
    expect(contentApiMocks.listContentTypes).toHaveBeenCalledTimes(2)
    expect(wrapper.findComponent(ContentModelForm).exists()).toBe(false)
  })

  it('offers a primary handoff action to create entries for a newly created model', async () => {
    const { wrapper, router } = await mountView()

    await wrapper.get('[data-testid="create-model"]').trigger('click')
    await flushPromises()

    wrapper.getComponent(ContentModelForm).vm.$emit('submit', {
      name: 'Landing pages',
      slug: 'landing-pages',
      description: null,
      field_definitions: deletableModel.field_definitions,
    })
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('Landing pages model created')
    expect(wrapper.text()).toContain('Create entries for this model now')

    await wrapper.get('[data-testid="create-entries-for-created-model"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/app/content')
    expect(router.currentRoute.value.query.contentTypeId).toBe('type-2')
  })

  it('updates a model and surfaces unsafe schema errors from the backend', async () => {
    contentApiMocks.updateContentType.mockRejectedValueOnce(
      new ApiClientError(409, 'body is required for existing entries', 'CONTENT_TYPE_UPDATE_INVALID'),
    )
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="edit-model-type-1"]').trigger('click')
    await flushPromises()

    wrapper.getComponent(ContentModelForm).vm.$emit('submit', {
      name: 'Articles',
      slug: 'articles',
      description: 'Changed',
      field_definitions: baseModel.field_definitions,
    })
    await flushPromises()

    expect(contentApiMocks.updateContentType).toHaveBeenCalledWith('type-1', {
      name: 'Articles',
      slug: 'articles',
      description: 'Changed',
      field_definitions: baseModel.field_definitions,
    })
    expect(wrapper.text()).toContain('Unsafe schema update blocked: body is required for existing entries')
  })

  it('visually separates destructive delete and blocks in-use models', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="edit-model-type-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delete-model"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Danger zone')

    wrapper.getComponent(ContentModelForm).vm.$emit('cancel')
    await flushPromises()
    await wrapper.get('[data-testid="edit-model-type-2"]').trigger('click')
    await flushPromises()
    wrapper.getComponent(ContentModelForm).vm.$emit('delete')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(contentApiMocks.deleteContentType).toHaveBeenCalledWith('type-2')
  })

  it('disables mutation affordances for read-only users', async () => {
    const { wrapper } = await mountView(['content.types.read'])

    expect(wrapper.text()).toContain('read-only access to content models')
    expect(wrapper.get('[data-testid="create-model"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="edit-model-type-1"]').attributes('disabled')).toBeDefined()
  })
})

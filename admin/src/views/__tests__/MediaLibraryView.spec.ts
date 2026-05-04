import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import MediaLibraryView from '@/views/MediaLibraryView.vue'

const mediaApiMocks = vi.hoisted(() => ({
  deleteMediaAsset: vi.fn(),
  fetchMediaVariantBlob: vi.fn(),
  listMediaAssets: vi.fn(),
  uploadMediaAsset: vi.fn(),
}))

vi.mock('@/api/media', () => mediaApiMocks)

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

class ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

vi.stubGlobal('ResizeObserver', ResizeObserver)

const mediaAsset = {
  id: 'media-1',
  original_filename: 'hero.png',
  storage_key: '2026/04/media-1-hero.png',
  mime_type: 'image/png',
  size_bytes: 68,
  width: 1,
  height: 1,
  alt_text: 'Hero image',
  caption: 'Homepage hero',
  description: null,
  variants: {
    thumbnail: '/api/v1/media/assets/media-1/variants/thumbnail',
  },
  uploader_user_id: null,
  created_at: '2026-04-21T00:00:00Z',
  updated_at: '2026-04-21T00:00:00Z',
  content_url: '/api/v1/media/assets/media-1/content',
  is_image: true,
  selection: {
    id: 'media-1',
    filename: 'hero.png',
    mime_type: 'image/png',
    width: 1,
    height: 1,
    alt_text: 'Hero image',
    content_url: '/api/v1/media/assets/media-1/content',
  },
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/app/media', name: 'media', component: MediaLibraryView }],
  })
}

async function mountView(permissions = [
  'media.assets.read',
  'media.assets.upload',
  'media.assets.delete',
]) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const authStore = useAuthStore()
  authStore.accessToken = 'token-123'
  authStore.user = {
    id: 'user-1',
    email: 'media@example.com',
    username: 'media-user',
    full_name: null,
    is_active: true,
    is_superuser: false,
    roles: ['media'],
    permissions,
    force_password_change: false,
  }

  const router = createTestRouter()
  await router.push('/app/media')
  await router.isReady()

  const wrapper = mount(MediaLibraryView, {
    global: {
      plugins: [pinia, router, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

  await flushPromises()
  await flushPromises()

  return { wrapper }
}

describe('MediaLibraryView', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    mediaApiMocks.listMediaAssets.mockResolvedValue({
      items: [mediaAsset],
      total: 1,
      limit: 50,
      offset: 0,
    })
    mediaApiMocks.fetchMediaVariantBlob.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    mediaApiMocks.uploadMediaAsset.mockResolvedValue(mediaAsset)
    mediaApiMocks.deleteMediaAsset.mockResolvedValue(undefined)

    Object.defineProperty(globalThis.URL, 'createObjectURL', {
      value: vi.fn(() => 'blob:hero'),
      configurable: true,
    })
    Object.defineProperty(globalThis.URL, 'revokeObjectURL', {
      value: vi.fn(),
      configurable: true,
    })
  })

  it('loads authenticated thumbnail variants as object URLs and revokes them on refresh and unmount', async () => {
    const createObjectUrl = vi.fn()
      .mockReturnValueOnce('blob:hero')
      .mockReturnValueOnce('blob:hero-refresh')
    Object.defineProperty(globalThis.URL, 'createObjectURL', {
      value: createObjectUrl,
      configurable: true,
    })

    const { wrapper } = await mountView()

    expect(mediaApiMocks.listMediaAssets).toHaveBeenCalledTimes(1)
    expect(mediaApiMocks.listMediaAssets).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
      order_by: 'updated_at',
    })
    expect(mediaApiMocks.fetchMediaVariantBlob).toHaveBeenCalledWith('media-1', 'thumbnail')
    expect(wrapper.get('img.media-library__thumb').attributes('src')).toBe('blob:hero')
    expect(wrapper.html()).not.toContain(mediaAsset.variants.thumbnail)
    expect(wrapper.html()).not.toContain(`src=\"${mediaAsset.content_url}\"`)
    expect(wrapper.text()).toContain('Media library')
    expect(wrapper.text()).toContain('hero.png')
    expect(wrapper.text()).toContain('Hero image')

    const refreshButton = wrapper.findAll('button').find((button) => button.text().includes('Refresh'))
    if (!refreshButton) {
      throw new Error('Refresh button not found')
    }

    await refreshButton.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith('blob:hero')
    expect(wrapper.get('img.media-library__thumb').attributes('src')).toBe('blob:hero-refresh')

    wrapper.unmount()

    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith('blob:hero-refresh')
  })
  it('shows an error when loading media fails instead of empty-state text', async () => {
    mediaApiMocks.listMediaAssets.mockRejectedValueOnce(new Error('Media service is unavailable'))

    const { wrapper } = await mountView()

    expect(mediaApiMocks.listMediaAssets).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Media service is unavailable')
    expect(wrapper.text()).not.toContain('No media has been uploaded yet.')
  })

  it('navigates backend media pages with visible range controls', async () => {
    const secondMediaAsset = {
      ...mediaAsset,
      id: 'media-2',
      original_filename: 'gallery.png',
      storage_key: '2026/04/media-2-gallery.png',
      alt_text: 'Gallery image',
      content_url: '/api/v1/media/assets/media-2/content',
      selection: {
        ...mediaAsset.selection,
        id: 'media-2',
        filename: 'gallery.png',
        alt_text: 'Gallery image',
        content_url: '/api/v1/media/assets/media-2/content',
      },
    }
    mediaApiMocks.listMediaAssets
      .mockResolvedValueOnce({
        items: [mediaAsset],
        total: 75,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [secondMediaAsset],
        total: 75,
        limit: 50,
        offset: 50,
      })

    const { wrapper } = await mountView()

    expect(wrapper.get('[data-testid="media-pagination-summary"]').text()).toContain('1-1 of 75')

    await wrapper.get('[data-testid="media-next"]').trigger('click')
    await flushPromises()

    expect(mediaApiMocks.listMediaAssets).toHaveBeenLastCalledWith({
      limit: 50,
      offset: 50,
      order_by: 'updated_at',
    })
    expect(wrapper.get('[data-testid="media-pagination-summary"]').text()).toContain('51-51 of 75')
    expect(wrapper.text()).toContain('gallery.png')
    expect(mediaApiMocks.fetchMediaVariantBlob).toHaveBeenCalledWith('media-2', 'thumbnail')
  })

  it('uploads the selected file with metadata and reloads the list', async () => {
    const { wrapper } = await mountView()
    const file = new File(['png'], 'upload.png', { type: 'image/png' })

    const fileInput = wrapper.get('input')
    Object.defineProperty(fileInput.element, 'files', {
      value: [file],
      configurable: true,
    })
    await fileInput.trigger('change')
    await wrapper.get('#media-alt-text').setValue('Upload alt')

    const uploadButton = wrapper.findAll('button').find((button) => button.text().includes('Upload now'))
    if (!uploadButton) {
      throw new Error('Upload button not found')
    }

    await uploadButton.trigger('click')
    await flushPromises()

    expect(mediaApiMocks.uploadMediaAsset).toHaveBeenCalledWith(file, {
      alt_text: 'Upload alt',
      caption: null,
      description: null,
    })
    expect(mediaApiMocks.listMediaAssets).toHaveBeenCalledTimes(2)
  })

  it('requires confirmation before deleting an asset from the table action', async () => {
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="media-delete"]').trigger('click')
    await flushPromises()

    expect(mediaApiMocks.deleteMediaAsset).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Delete hero.png?')

    const confirmButton = document.body.querySelector('[data-testid="media-confirm-delete"]')
    if (!(confirmButton instanceof HTMLButtonElement)) {
      throw new Error('Delete confirmation button not found')
    }

    confirmButton.click()
    await flushPromises()
    await flushPromises()

    expect(mediaApiMocks.deleteMediaAsset).toHaveBeenCalledWith('media-1')
  })

  it('keeps read-only browsing while disabling upload and delete controls without permissions', async () => {
    const { wrapper } = await mountView(['media.assets.read'])

    expect(wrapper.text()).toContain('hero.png')
    expect(wrapper.text()).toContain('Uploading media requires the media.assets.upload permission.')
    expect(wrapper.text()).toContain('Deleting media requires the media.assets.delete permission.')
    expect(wrapper.get('[data-testid="media-choose-file"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="media-upload-now"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="media-delete"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('input[type="file"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="media-delete"]').trigger('click')
    await flushPromises()

    expect(mediaApiMocks.uploadMediaAsset).not.toHaveBeenCalled()
    expect(mediaApiMocks.deleteMediaAsset).not.toHaveBeenCalled()
  })
})

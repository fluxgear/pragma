import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createMemoryHistory, createRouter } from 'vue-router'

import MediaLibraryView from '@/views/MediaLibraryView.vue'

const mediaApiMocks = vi.hoisted(() => ({
  deleteMediaAsset: vi.fn(),
  fetchMediaContentBlob: vi.fn(),
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
  variants: {},
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

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

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
    vi.clearAllMocks()
    mediaApiMocks.listMediaAssets.mockResolvedValue({
      items: [mediaAsset],
      total: 1,
      limit: 50,
      offset: 0,
    })
    mediaApiMocks.fetchMediaContentBlob.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
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

  it('loads media assets and image previews on mount', async () => {
    const { wrapper } = await mountView()

    expect(mediaApiMocks.listMediaAssets).toHaveBeenCalledTimes(1)
    expect(mediaApiMocks.fetchMediaContentBlob).toHaveBeenCalledWith('media-1')
    expect(wrapper.text()).toContain('Media library')
    expect(wrapper.text()).toContain('hero.png')
    expect(wrapper.text()).toContain('Hero image')
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

  it('deletes an asset from the table action', async () => {
    const { wrapper } = await mountView()

    const deleteButton = wrapper.findAll('button').find((button) => button.text().includes('Delete'))
    if (!deleteButton) {
      throw new Error('Delete button not found')
    }

    await deleteButton.trigger('click')
    await flushPromises()

    expect(mediaApiMocks.deleteMediaAsset).toHaveBeenCalledWith('media-1')
  })
})

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import { ApiClientError } from '@/api/errors'
import type { BlockDocument, BlockDocumentFieldDefinition, ContentEntryResponse, ContentTypeResponse } from '@/api/types'

const aiApiMocks = vi.hoisted(() => ({
  generateAiText: vi.fn(),
}))

vi.mock('@/api/ai', () => aiApiMocks)

import BlockEditorShell from '@/components/content/blocks/BlockEditorShell.vue'

const blockDocument: BlockDocument = {
  version: 1,
  root: {
    type: 'section',
    props: {},
    settings: { width: 'wide', background: 'none' },
    children: [
      {
        type: 'container',
        props: {},
        settings: {},
        children: [
          { type: 'heading', props: { text: 'Hello Blocks', level: 2 }, settings: {}, children: [] },
          { type: 'paragraph', props: { html: '<p>Body copy</p>' }, settings: {}, children: [] },
        ],
      },
    ],
  },
}

const blockField: BlockDocumentFieldDefinition = {
  name: 'body',
  label: 'Body',
  kind: 'block_document',
  required: false,
  help_text: 'Page composition body.',
}

const contentType: ContentTypeResponse = {
  id: 'type-block',
  name: 'Pages',
  slug: 'pages',
  description: null,
  entry_count: 1,
  can_delete: false,
  field_definitions: [blockField],
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-05-06T00:00:00Z',
  updated_at: '2026-05-06T00:00:00Z',
}

const entry: ContentEntryResponse = {
  id: 'entry-block',
  content_type_id: 'type-block',
  content_type_slug: 'pages',
  slug: 'home',
  status: 'draft',
  payload: { body: blockDocument },
  published_at: null,
  created_by_user_id: null,
  updated_by_user_id: null,
  created_at: '2026-05-06T00:00:00Z',
  updated_at: '2026-05-06T00:00:00Z',
}

function mountShell(props: Partial<InstanceType<typeof BlockEditorShell>['$props']> = {}) {
  return mount(BlockEditorShell, {
    props: { contentType, blockFields: [blockField], entry: null, ...props },
    global: { plugins: [[PrimeVue, { theme: { preset: Aura } }]] },
  })
}

async function addBlock(wrapper: ReturnType<typeof mountShell>, type: string) {
  await wrapper.get('[data-testid="block-add-type"]').setValue(type)
  await wrapper.get('[data-testid="block-add"]').trigger('click')
}

async function insertPattern(wrapper: ReturnType<typeof mountShell>, type: string) {
  await wrapper.get('[data-testid="block-pattern-type"]').setValue(type)
  await wrapper.get('[data-testid="block-pattern-add"]').trigger('click')
}

function generationResponse(text: string) {
  return {
    provider: 'openai_compatible',
    api_mode: 'chat_completions',
    model: 'gpt-5-mini',
    text,
    finish_reason: 'stop',
    usage: null,
  }
}

describe('BlockEditorShell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  it('shows an empty local draft for new block-document entries', () => {
    const wrapper = mountShell()

    expect(wrapper.text()).toContain('New Pages block entry')
    expect(wrapper.text()).toContain('Draft save enabled')
    expect(wrapper.text()).toContain('New local draft')
    expect(wrapper.get('[data-testid="block-tree"]').text()).toContain('Section block')
  })

  it('loads an existing document into the tree and visual canvas', () => {
    const wrapper = mountShell({ entry })

    expect(wrapper.text()).toContain('Editing home')
    expect(wrapper.get('[data-testid="block-field-body"]').text()).toContain('Existing document')
    expect(wrapper.get('[data-testid="block-field-body"]').text()).toContain('4')
    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Hello Blocks')
    expect(wrapper.get('[data-testid="block-tree"]').text()).toContain('heading')
  })

  it('adds baseline blocks, configures heading props/settings, and emits a normalized save document', async () => {
    const wrapper = mountShell()

    await addBlock(wrapper, 'heading')
    expect(wrapper.get('[data-testid="block-tree"]').text()).toContain('New heading')

    await wrapper.get('[data-testid="inspector-heading-text"]').setValue('Configured heading')
    await wrapper.get('[data-testid="inspector-heading-level"]').setValue('3')
    await wrapper.get('[data-testid="inspector-align"]').setValue('center')
    await wrapper.get('[data-testid="block-editor-save"]').trigger('click')

    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Configured heading')
    expect(wrapper.emitted('draft-change')).toBeTruthy()
    expect(wrapper.emitted('save')?.[0]).toEqual([
      expect.objectContaining({
        version: 1,
        root: expect.objectContaining({
          type: 'section',
          props: {},
          settings: expect.any(Object),
          children: [
            expect.objectContaining({
              type: 'heading',
              props: expect.objectContaining({ text: 'Configured heading', level: 3 }),
              settings: expect.objectContaining({ align: 'center' }),
              children: [],
            }),
          ],
        }),
      }),
    ])
  })

  it('duplicates, deletes, and reorders selected blocks with keyboard-reachable controls', async () => {
    const wrapper = mountShell()

    await addBlock(wrapper, 'heading')
    await wrapper.get('[data-testid="inspector-heading-text"]').setValue('First heading')
    await addBlock(wrapper, 'paragraph')
    await wrapper.get('[data-testid="block-move-up"]').trigger('click')

    let treeText = wrapper.get('[data-testid="block-tree"]').text()
    expect(treeText.indexOf('Start writing paragraph text.')).toBeLessThan(treeText.indexOf('First heading'))

    await wrapper.get('[data-testid="block-duplicate"]').trigger('click')
    expect(wrapper.findAll('[data-testid="tree-node-paragraph"]')).toHaveLength(2)

    await wrapper.get('[data-testid="block-delete"]').trigger('click')
    expect(wrapper.findAll('[data-testid="tree-node-paragraph"]')).toHaveLength(1)
  })

  it('edits image, button, list, and card basics from the inspector', async () => {
    const wrapper = mountShell()

    await addBlock(wrapper, 'image')
    await wrapper.get('[data-testid="inspector-image-media-id"]').setValue('1c59b3c9-09e7-4562-8d6b-6ebc8f82758b')
    await wrapper.get('[data-testid="inspector-image-alt"]').setValue('Editorial image')
    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Editorial image')

    await addBlock(wrapper, 'button')
    await wrapper.get('[data-testid="inspector-button-label"]').setValue('Read more')
    await wrapper.get('[data-testid="inspector-button-href"]').setValue('/read-more')
    await wrapper.get('[data-testid="inspector-button-variant"]').setValue('secondary')
    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Read more')

    await addBlock(wrapper, 'list')
    await wrapper.get('[data-testid="inspector-list-style"]').setValue('ordered')
    await wrapper.get('[data-testid="inspector-list-items"]').setValue('One\nTwo')
    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Two')

    await addBlock(wrapper, 'card')
    await wrapper.get('[data-testid="inspector-card-variant"]').setValue('elevated')
    expect(wrapper.get('[data-testid="block-tree"]').text()).toContain('Card block')
  })


  it('inserts hero CTA pattern with normalized nodes and saves expected payload shape', async () => {
    const wrapper = mountShell()

    await insertPattern(wrapper, 'hero-cta')
    await wrapper.get('[data-testid="block-editor-save"]').trigger('click')

    const payload = wrapper.emitted('save')?.[0]?.[0] as BlockDocument
    expect(payload.version).toBe(1)
    expect(payload.root.type).toBe('section')
    expect(payload.root.children[0]?.type).toBe('section')

    const assertNormalized = (node: any): void => {
      expect(node).toHaveProperty('props')
      expect(node).toHaveProperty('settings')
      expect(node).toHaveProperty('children')
      expect(Array.isArray(node.children)).toBe(true)
      node.children.forEach(assertNormalized)
    }

    assertNormalized(payload.root)
    expect(wrapper.get('[data-testid="block-tree"]').text()).toContain('Build your next launch page faster')
    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Start now')
  })

  it('switches responsive preview modes', async () => {
    const wrapper = mountShell({ entry })

    expect(wrapper.get('[data-testid="block-preview-frame"]').attributes('data-preview-mode')).toBe('desktop')
    await wrapper.get('[data-testid="preview-tablet"]').trigger('click')
    expect(wrapper.get('[data-testid="block-preview-frame"]').attributes('data-preview-mode')).toBe('tablet')
    await wrapper.get('[data-testid="preview-mobile"]').trigger('click')
    expect(wrapper.get('[data-testid="block-preview-frame"]').attributes('data-preview-mode')).toBe('mobile')
  })

  it('shows validation messages for empty required values', async () => {
    const wrapper = mountShell()

    await addBlock(wrapper, 'image')

    expect(wrapper.get('[data-testid="block-validation-messages"]').text()).toContain('Image alt text is required')
    expect(wrapper.get('[data-testid="block-validation-messages"]').text()).toContain('media ID or image URL')

    await wrapper.get('[data-testid="inspector-image-alt"]').setValue('Hero image')
    await wrapper.get('[data-testid="inspector-image-src"]').setValue('/media/hero.jpg')

    expect(wrapper.find('[data-testid="block-validation-messages"]').exists()).toBe(false)
  })

  it('requests backend editor generation and does not mutate before accept', async () => {
    aiApiMocks.generateAiText.mockResolvedValue(generationResponse('Improved body copy.'))
    const wrapper = mountShell({ entry })

    await wrapper.get('[data-testid="tree-node-paragraph"]').trigger('click')
    await wrapper.get('[data-testid="block-ai-action"]').setValue('rewrite-selected')
    await wrapper.get('[data-testid="block-ai-generate"]').trigger('click')
    await flushPromises()

    expect(aiApiMocks.generateAiText).toHaveBeenCalledWith(expect.objectContaining({
      scope: 'editor',
      instructions: expect.stringContaining('Rewrite'),
      max_output_tokens: 96,
    }))
    expect(aiApiMocks.generateAiText.mock.calls[0][0].input).toContain('Selected block: paragraph')
    expect(wrapper.get('[data-testid="block-ai-suggestion"]').text()).toContain('Improved body copy.')
    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Body copy')
    expect(wrapper.emitted('draft-change')).toBeUndefined()

    await wrapper.get('[data-testid="block-ai-accept"]').trigger('click')

    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).toContain('Improved body copy.')
    expect(wrapper.emitted('draft-change')).toBeTruthy()
    expect(wrapper.emitted('save')).toBeUndefined()
  })

  it('dismisses generated suggestions without mutating the local draft', async () => {
    aiApiMocks.generateAiText.mockResolvedValue(generationResponse('Book a demo'))
    const wrapper = mountShell({ entry })

    await wrapper.get('[data-testid="block-ai-action"]').setValue('suggest-cta')
    await wrapper.get('[data-testid="block-ai-generate"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="block-ai-suggestion"]').text()).toContain('Book a demo')
    await wrapper.get('[data-testid="block-ai-dismiss"]').trigger('click')

    expect(wrapper.find('[data-testid="block-ai-suggestion"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="block-editor-canvas-summary"]').text()).not.toContain('Book a demo')
    expect(wrapper.emitted('draft-change')).toBeUndefined()
  })

  it.each([
    [
      'provider unavailable',
      new ApiClientError(400, 'AI provider is disabled', 'AI_SETTINGS_DISABLED'),
      'Provider unavailable: AI provider is disabled',
    ],
    [
      'permission denied',
      new ApiClientError(403, 'Missing permission: ai.editor_assist', 'PERMISSION_DENIED'),
      'Permission denied: Missing permission: ai.editor_assist',
    ],
    [
      'backend failure',
      new Error('Network down'),
      'Backend failure: Network down',
    ],
  ])('shows %s AI generation errors without mutating', async (_label, error, expectedMessage) => {
    aiApiMocks.generateAiText.mockRejectedValue(error)
    const wrapper = mountShell({ entry })

    await wrapper.get('[data-testid="block-ai-generate"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="block-ai-error"]').text()).toContain(expectedMessage)
    expect(wrapper.find('[data-testid="block-ai-suggestion"]').exists()).toBe(false)
    expect(wrapper.emitted('draft-change')).toBeUndefined()
  })

  it('renders read-only block entries without allowing draft mutations, save, or AI generation', async () => {
    const wrapper = mountShell({ entry, readOnly: true })

    expect(wrapper.text()).toContain('Read-only preview')
    expect(wrapper.get('[data-testid="block-editor-read-only-copy"]').text()).toContain('saving requires content.entries.write')
    expect(wrapper.get('[data-testid="block-editor-ai-read-only"]').text()).toContain('AI suggestions are unavailable')
    expect(wrapper.get('[data-testid="block-editor-save"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="block-add"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="block-ai-generate"]').exists()).toBe(false)

    await wrapper.get('[data-testid="block-add"]').trigger('click')
    await wrapper.get('[data-testid="block-editor-save"]').trigger('click')

    expect(aiApiMocks.generateAiText).not.toHaveBeenCalled()
    expect(wrapper.emitted('draft-change')).toBeUndefined()
    expect(wrapper.emitted('save')).toBeUndefined()
  })

  it('shows active safe AI assist controls instead of deferred copy', () => {
    const wrapper = mountShell({ entry })

    expect(wrapper.get('[data-testid="block-editor-ai-panel"]').text()).toContain('backend /ai/generate editor scope')
    expect(wrapper.get('[data-testid="block-ai-action"]').text()).toContain('Draft page intro')
    expect(wrapper.find('[data-testid="block-editor-ai-copy"]').exists()).toBe(false)
  })
})

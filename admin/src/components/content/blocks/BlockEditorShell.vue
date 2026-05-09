<template>
  <section class="block-editor-shell" aria-labelledby="block-editor-title">
    <div class="block-editor-shell__header">
      <div>
        <p class="muted">Visual block editor MVP</p>
        <h2 id="block-editor-title">{{ title }}</h2>
        <p class="muted">
          Compose a normalized block document, save it as a draft, and reload existing block entries through the content API.
        </p>
      </div>
      <div class="inline-actions">
        <Tag :value="statusLabel" :severity="readOnly ? 'warn' : 'success'" />
        <Button
          type="button"
          label="Save draft"
          icon="pi pi-save"
          data-testid="block-editor-save"
          :disabled="editorControlsDisabled"
          :loading="saving"
          :title="saveDisabledReason"
          @click="saveDraft"
        />
        <Button type="button" label="Close" severity="secondary" variant="outlined" @click="emit('close')" />
      </div>
    </div>

    <Message v-if="errorMessage" severity="error" :closable="false" data-testid="block-editor-error">
      {{ errorMessage }}
    </Message>

    <section class="block-editor-shell__ai-panel" aria-labelledby="block-editor-ai-title" data-testid="block-editor-ai-panel">
      <div class="block-editor-shell__ai-header">
        <div>
          <p class="muted">AI assist</p>
          <h3 id="block-editor-ai-title">Draft suggestion assistant</h3>
          <p class="muted">
            Uses the backend /ai/generate editor scope only. Suggestions stay in this local draft until you accept them.
          </p>
        </div>
        <Tag value="Review before accepting" severity="info" />
      </div>

      <Message v-if="readOnly" severity="warn" :closable="false" data-testid="block-editor-ai-read-only">
        AI suggestions are unavailable in read-only preview. No AI action can mutate this draft without edit permission.
      </Message>

      <div v-else class="form-stack">
        <div class="block-editor-shell__ai-controls">
          <div class="field block-editor-shell__command-field">
            <label for="block-ai-action">AI action</label>
            <select
              id="block-ai-action"
              v-model="selectedAiAction"
              class="content-model-builder__native-control"
              data-testid="block-ai-action"
              :disabled="editorControlsDisabled || aiGenerating"
            >
              <option v-for="action in aiActions" :key="action.value" :value="action.value">
                {{ action.label }}
              </option>
            </select>
            <small class="muted" data-testid="block-ai-action-description">{{ aiActionDescription }}</small>
          </div>
          <Button
            type="button"
            label="Generate suggestion"
            icon="pi pi-sparkles"
            data-testid="block-ai-generate"
            :disabled="aiGenerateDisabled"
            :loading="aiGenerating"
            @click="requestAiSuggestion"
          />
        </div>

        <Message v-if="aiErrorMessage" severity="error" :closable="false" data-testid="block-ai-error">
          {{ aiErrorMessage }}
        </Message>

        <article v-if="aiSuggestion" class="block-editor-shell__ai-review" data-testid="block-ai-suggestion">
          <div>
            <strong>{{ aiSuggestionLabel }}</strong>
            <p class="muted">Accept updates the local draft only; it does not save or publish.</p>
          </div>
          <blockquote>{{ aiSuggestion.text }}</blockquote>
          <div class="inline-actions">
            <Button type="button" label="Accept suggestion" icon="pi pi-check" data-testid="block-ai-accept" :disabled="editorControlsDisabled" @click="acceptAiSuggestion" />
            <Button type="button" label="Dismiss" severity="secondary" variant="outlined" data-testid="block-ai-dismiss" @click="dismissAiSuggestion" />
          </div>
        </article>
        <p v-else class="muted" data-testid="block-ai-empty">Generated suggestions appear here for review before they can change the draft.</p>
      </div>
    </section>

    <Message v-if="readOnly" severity="warn" :closable="false" data-testid="block-editor-read-only-copy">
      You can review this block document, but saving requires content.entries.write permission and publish permission for published entries.
    </Message>

    <Message v-else severity="success" :closable="false" data-testid="block-editor-save-copy">
      Changes are saved through the existing content entry create/update API as a draft block document.
    </Message>

    <div class="block-editor-shell__field-strip" aria-label="Block document fields">
      <article
        v-for="fieldSummary in fieldSummaries"
        :key="fieldSummary.name"
        class="block-editor-shell__field-card"
        :data-testid="`block-field-${fieldSummary.name}`"
      >
        <div>
          <h3>{{ fieldSummary.label }}</h3>
          <p class="muted">{{ fieldSummary.name }} · block_document</p>
        </div>
        <Tag :value="fieldSummary.stateLabel" :severity="fieldSummary.document === null ? 'warn' : 'success'" />
        <p v-if="fieldSummary.helpText" class="muted">{{ fieldSummary.helpText }}</p>
        <dl class="block-editor-shell__stats">
          <div>
            <dt>Blocks</dt>
            <dd>{{ blockCount }}</dd>
          </div>
          <div>
            <dt>Max depth</dt>
            <dd>{{ maxDepth }}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>v{{ draftDocument.version }}</dd>
          </div>
        </dl>
      </article>
      <div v-if="fieldSummaries.length === 0" class="block-editor-shell__empty muted">
        No block-document fields are configured for this content type.
      </div>
    </div>

    <div class="block-editor-shell__toolbar" aria-label="Editor controls">
      <div class="field block-editor-shell__command-field">
        <label for="block-add-type">Add block</label>
        <div class="inline-actions">
          <select id="block-add-type" v-model="selectedAddType" class="content-model-builder__native-control" data-testid="block-add-type" :disabled="editorControlsDisabled">
            <option v-for="blockType in addableBlockTypes" :key="blockType.type" :value="blockType.type">
              {{ blockType.label }}
            </option>
          </select>
          <Button type="button" label="Add block" icon="pi pi-plus" data-testid="block-add" :disabled="editorControlsDisabled" @click="addBlock(selectedAddType)" />
        </div>
        <small class="muted">Adds inside layout blocks or as a sibling near the selected block.</small>
      </div>

      <div class="field block-editor-shell__command-field">
        <label for="block-pattern-type">Insert pattern</label>
        <div class="inline-actions">
          <select id="block-pattern-type" v-model="selectedPatternType" class="content-model-builder__native-control" data-testid="block-pattern-type" :disabled="editorControlsDisabled">
            <option v-for="pattern in insertablePatterns" :key="pattern.type" :value="pattern.type">
              {{ pattern.label }}
            </option>
          </select>
          <Button type="button" label="Insert pattern" icon="pi pi-clone" data-testid="block-pattern-add" :disabled="editorControlsDisabled" @click="insertPattern(selectedPatternType)" />
        </div>
        <small class="muted">Inserts a reusable baseline layout using existing blocks.</small>
      </div>

      <fieldset class="block-editor-shell__preview-toggle" aria-label="Responsive preview mode">
        <legend>Preview width</legend>
        <div class="inline-actions">
          <button
            v-for="mode in previewModes"
            :key="mode.value"
            type="button"
            class="block-editor-shell__mode-button"
            :class="{ 'block-editor-shell__mode-button--active': previewMode === mode.value }"
            :aria-pressed="previewMode === mode.value"
            :data-testid="`preview-${mode.value}`"
            @click="previewMode = mode.value"
          >
            {{ mode.label }}
          </button>
        </div>
      </fieldset>
    </div>

    <div class="block-editor-shell__grid block-editor-shell__grid--editor">
      <Card class="block-editor-shell__panel">
        <template #title>Block tree</template>
        <template #content>
          <div class="block-editor-shell__tree" data-testid="block-tree">
            <article
              v-for="item in flatNodes"
              :key="item.key"
              class="block-editor-shell__tree-row"
              :class="{ 'block-editor-shell__tree-row--selected': item.key === selectedKey }"
              :style="{ marginLeft: `${item.depth * 0.9}rem` }"
            >
              <button
                type="button"
                class="block-editor-shell__tree-select"
                :aria-current="item.key === selectedKey ? 'true' : undefined"
                :data-testid="`tree-node-${item.node.type}`"
                @click="selectPath(item.path)"
              >
                <strong>{{ blockLabel(item.node) }}</strong>
                <span class="muted">{{ item.node.type }} · {{ childNodes(item.node).length }} children</span>
              </button>
              <div class="inline-actions block-editor-shell__row-actions" :aria-label="`${item.node.type} reorder actions`">
                <Button
                  type="button"
                  label="Up"
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  :disabled="editorControlsDisabled || !canMove(item.path, -1)"
                  :data-testid="`move-up-${item.node.type}`"
                  @click="moveBlock(item.path, -1)"
                />
                <Button
                  type="button"
                  label="Down"
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  :disabled="editorControlsDisabled || !canMove(item.path, 1)"
                  :data-testid="`move-down-${item.node.type}`"
                  @click="moveBlock(item.path, 1)"
                />
              </div>
            </article>
          </div>
        </template>
      </Card>

      <Card class="block-editor-shell__canvas-card">
        <template #title>Visual canvas</template>
        <template #content>
          <div
            class="block-editor-shell__preview-frame"
            :class="`block-editor-shell__preview-frame--${previewMode}`"
            :data-preview-mode="previewMode"
            data-testid="block-preview-frame"
          >
            <div class="block-editor-shell__canvas" data-testid="block-editor-canvas-summary">
              <div v-if="draftDocument.root.children.length === 0" class="block-editor-shell__canvas-empty" data-testid="block-editor-empty-state">
                <i class="pi pi-sitemap" aria-hidden="true"></i>
                <h3>No block document content yet</h3>
                <p class="muted">Use Add block to start composing a local draft.</p>
              </div>
              <BlockPreview :node="draftDocument.root" :path="[]" />
            </div>
          </div>
        </template>
      </Card>

      <Card class="block-editor-shell__inspector-card">
        <template #title>Inspector</template>
        <template #content>
          <div v-if="selectedNode" class="form-stack" data-testid="block-inspector">
            <div>
              <p class="muted">Selected block</p>
              <h3>{{ blockLabel(selectedNode) }}</h3>
              <p class="muted">{{ selectedNode.type }}</p>
            </div>

            <div class="block-editor-shell__inspector-actions">
              <Button type="button" label="Duplicate" severity="secondary" variant="outlined" data-testid="block-duplicate" :disabled="editorControlsDisabled || isRootSelected" @click="duplicateSelectedBlock" />
              <Button type="button" label="Delete" severity="danger" variant="outlined" data-testid="block-delete" :disabled="editorControlsDisabled || isRootSelected" @click="deleteSelectedBlock" />
              <Button type="button" label="Move up" severity="secondary" variant="outlined" data-testid="block-move-up" :disabled="editorControlsDisabled || !canMove(selectedPath, -1)" @click="moveBlock(selectedPath, -1)" />
              <Button type="button" label="Move down" severity="secondary" variant="outlined" data-testid="block-move-down" :disabled="editorControlsDisabled || !canMove(selectedPath, 1)" @click="moveBlock(selectedPath, 1)" />
            </div>

            <fieldset class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>Common settings</legend>
              <div v-if="supportsAlign(selectedNode.type)" class="field">
                <label for="block-align">Alignment</label>
                <select id="block-align" class="content-model-builder__native-control" :value="stringSetting('align', 'left')" data-testid="inspector-align" @change="updateSetting('align', eventValue($event))">
                  <option v-for="align in alignOptions(selectedNode.type)" :key="align" :value="align">{{ align }}</option>
                </select>
              </div>
              <div v-if="selectedNode.type === 'section' || selectedNode.type === 'container'" class="field">
                <label for="block-width">Width</label>
                <select id="block-width" class="content-model-builder__native-control" :value="stringSetting('width', 'wide')" data-testid="inspector-width" @change="updateSetting('width', eventValue($event))">
                  <option value="full">Full</option>
                  <option value="wide">Wide</option>
                  <option value="narrow">Narrow</option>
                </select>
              </div>
              <div v-if="selectedNode.type === 'section' || selectedNode.type === 'container'" class="field">
                <label for="block-background">Background</label>
                <select id="block-background" class="content-model-builder__native-control" :value="stringSetting('background', 'none')" data-testid="inspector-background" @change="updateSetting('background', eventValue($event))">
                  <option value="none">None</option>
                  <option value="muted">Muted</option>
                  <option value="accent">Accent</option>
                </select>
              </div>
            </fieldset>

            <fieldset v-if="selectedNode.type === 'heading'" class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>Heading</legend>
              <div class="field">
                <label for="heading-text">Text</label>
                <input id="heading-text" class="content-model-builder__native-control" :value="stringProp('text')" data-testid="inspector-heading-text" @input="updateProp('text', eventValue($event))" />
              </div>
              <div class="field">
                <label for="heading-level">Level</label>
                <select id="heading-level" class="content-model-builder__native-control" :value="numberProp('level', 2)" data-testid="inspector-heading-level" @change="updateProp('level', Number(eventValue($event)))">
                  <option v-for="level in [1, 2, 3, 4, 5, 6]" :key="level" :value="level">Heading {{ level }}</option>
                </select>
              </div>
            </fieldset>

            <fieldset v-else-if="selectedNode.type === 'paragraph'" class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>Paragraph</legend>
              <div class="field">
                <label for="paragraph-html">Text / simple HTML</label>
                <textarea id="paragraph-html" class="content-model-builder__native-control" rows="5" :value="stringProp('html')" data-testid="inspector-paragraph-html" @input="updateProp('html', eventValue($event))"></textarea>
              </div>
            </fieldset>

            <fieldset v-else-if="selectedNode.type === 'image'" class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>Image media</legend>
              <div class="field">
                <label for="image-media-id">Media ID</label>
                <input id="image-media-id" class="content-model-builder__native-control" :value="stringProp('media_id')" data-testid="inspector-image-media-id" placeholder="Existing media UUID" @input="updateProp('media_id', eventValue($event))" />
              </div>
              <div class="field">
                <label for="image-src">Image URL</label>
                <input id="image-src" class="content-model-builder__native-control" :value="stringProp('src')" data-testid="inspector-image-src" placeholder="https://example.test/image.jpg" @input="updateProp('src', eventValue($event))" />
              </div>
              <div class="field">
                <label for="image-alt">Alt text</label>
                <input id="image-alt" class="content-model-builder__native-control" :value="stringProp('alt')" data-testid="inspector-image-alt" @input="updateProp('alt', eventValue($event))" />
              </div>
              <div class="field">
                <label for="image-caption">Caption</label>
                <input id="image-caption" class="content-model-builder__native-control" :value="stringProp('caption')" data-testid="inspector-image-caption" @input="updateProp('caption', eventValue($event))" />
              </div>
            </fieldset>

            <fieldset v-else-if="selectedNode.type === 'button'" class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>Button</legend>
              <div class="field">
                <label for="button-label">Label</label>
                <input id="button-label" class="content-model-builder__native-control" :value="stringProp('label')" data-testid="inspector-button-label" @input="updateProp('label', eventValue($event))" />
              </div>
              <div class="field">
                <label for="button-href">Link URL</label>
                <input id="button-href" class="content-model-builder__native-control" :value="stringProp('href')" data-testid="inspector-button-href" @input="updateProp('href', eventValue($event))" />
              </div>
              <div class="field">
                <label for="button-variant">Variant</label>
                <select id="button-variant" class="content-model-builder__native-control" :value="stringSetting('variant', 'primary')" data-testid="inspector-button-variant" @change="updateSetting('variant', eventValue($event))">
                  <option value="primary">Primary</option>
                  <option value="secondary">Secondary</option>
                  <option value="link">Link</option>
                </select>
              </div>
            </fieldset>

            <fieldset v-else-if="selectedNode.type === 'list'" class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>List</legend>
              <div class="field">
                <label for="list-style">Style</label>
                <select id="list-style" class="content-model-builder__native-control" :value="stringProp('style', 'unordered')" data-testid="inspector-list-style" @change="updateProp('style', eventValue($event))">
                  <option value="unordered">Unordered</option>
                  <option value="ordered">Ordered</option>
                </select>
              </div>
              <div class="field">
                <label for="list-items">Items, one per line</label>
                <textarea id="list-items" class="content-model-builder__native-control" rows="5" :value="listItemsText" data-testid="inspector-list-items" @input="updateListItems(eventValue($event))"></textarea>
              </div>
            </fieldset>

            <fieldset v-else-if="selectedNode.type === 'card'" class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>Card</legend>
              <div class="field">
                <label for="card-variant">Variant</label>
                <select id="card-variant" class="content-model-builder__native-control" :value="stringSetting('variant', 'outlined')" data-testid="inspector-card-variant" @change="updateSetting('variant', eventValue($event))">
                  <option value="plain">Plain</option>
                  <option value="outlined">Outlined</option>
                  <option value="elevated">Elevated</option>
                </select>
              </div>
            </fieldset>

            <fieldset v-else-if="selectedNode.type === 'spacer'" class="form-stack block-editor-shell__fieldset" :disabled="editorControlsDisabled">
              <legend>Spacer</legend>
              <div class="field">
                <label for="spacer-size">Size</label>
                <select id="spacer-size" class="content-model-builder__native-control" :value="stringProp('size', 'medium')" data-testid="inspector-spacer-size" @change="updateProp('size', eventValue($event))">
                  <option value="small">Small</option>
                  <option value="medium">Medium</option>
                  <option value="large">Large</option>
                </select>
              </div>
            </fieldset>

            <div v-if="selectedValidationMessages.length > 0" class="block-editor-shell__validation" data-testid="block-validation-messages" role="alert">
              <strong>Validation issues</strong>
              <ul>
                <li v-for="message in selectedValidationMessages" :key="message">{{ message }}</li>
              </ul>
            </div>
          </div>
        </template>
      </Card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, ref, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import { generateAiText } from '@/api/ai'
import { ApiClientError, asUserMessage } from '@/api/errors'
import type { BlockDocument, BlockDocumentFieldDefinition, BlockNode, ContentEntryResponse, ContentTypeResponse } from '@/api/types'

const props = withDefaults(defineProps<{
  contentType: ContentTypeResponse
  entry?: ContentEntryResponse | null
  blockFields: BlockDocumentFieldDefinition[]
  readOnly?: boolean
  saving?: boolean
  errorMessage?: string | null
}>(), {
  entry: null,
  readOnly: false,
  saving: false,
  errorMessage: null,
})
const emit = defineEmits<{
  close: []
  save: [document: BlockDocument]
  'draft-change': [document: BlockDocument]
}>()

type BlockType =
  | 'section'
  | 'container'
  | 'columns'
  | 'heading'
  | 'paragraph'
  | 'image'
  | 'button'
  | 'divider'
  | 'spacer'
  | 'quote'
  | 'list'
  | 'card'

type PreviewMode = 'desktop' | 'tablet' | 'mobile'
type PatternType = 'hero-cta' | 'services-grid' | 'testimonials-strip' | 'team-grid' | 'cta-banner'
type AiAction = 'page-intro' | 'rewrite-selected' | 'suggest-cta'

type FlatNode = {
  node: BlockNode
  path: number[]
  depth: number
  key: string
}

type ValidationItem = {
  key: string
  message: string
}

type AiSuggestion = {
  action: AiAction
  targetPath: number[]
  targetType: string
  text: string
}

const addableBlockTypes: Array<{ type: BlockType; label: string }> = [
  { type: 'section', label: 'Section' },
  { type: 'container', label: 'Container' },
  { type: 'columns', label: 'Columns' },
  { type: 'heading', label: 'Heading' },
  { type: 'paragraph', label: 'Paragraph' },
  { type: 'image', label: 'Image' },
  { type: 'button', label: 'Button' },
  { type: 'divider', label: 'Divider' },
  { type: 'spacer', label: 'Spacer' },
  { type: 'quote', label: 'Quote' },
  { type: 'list', label: 'List' },
  { type: 'card', label: 'Card' },
]

const previewModes: Array<{ value: PreviewMode; label: string }> = [
  { value: 'desktop', label: 'Desktop' },
  { value: 'tablet', label: 'Tablet' },
  { value: 'mobile', label: 'Mobile' },
]

const insertablePatterns: Array<{ type: PatternType; label: string }> = [
  { type: 'hero-cta', label: 'Hero CTA' },
  { type: 'services-grid', label: 'Services / feature grid' },
  { type: 'testimonials-strip', label: 'Testimonials strip' },
  { type: 'team-grid', label: 'Team grid' },
  { type: 'cta-banner', label: 'CTA banner' },
]

const aiActions: Array<{ value: AiAction; label: string }> = [
  { value: 'page-intro', label: 'Draft page intro' },
  { value: 'rewrite-selected', label: 'Rewrite selected block' },
  { value: 'suggest-cta', label: 'Suggest CTA button' },
]

const selectedAddType = ref<BlockType>('heading')
const selectedPatternType = ref<PatternType>('hero-cta')
const selectedAiAction = ref<AiAction>('page-intro')
const selectedPath = ref<number[]>([])
const previewMode = ref<PreviewMode>('desktop')
const draftDocument = ref<BlockDocument>(createInitialDocument())
const aiGenerating = ref(false)
const aiErrorMessage = ref<string | null>(null)
const aiSuggestion = ref<AiSuggestion | null>(null)

interface FieldSummary {
  name: string
  label: string
  helpText: string | null
  document: BlockDocument | null
  stateLabel: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isBlockNode(value: unknown): value is BlockNode {
  return isRecord(value) && typeof value.type === 'string'
}

function isBlockDocument(value: unknown): value is BlockDocument {
  return isRecord(value) && value.version === 1 && isBlockNode(value.root)
}

function normalizeNode(node: BlockNode): BlockNode {
  return {
    type: node.type,
    props: isRecord(node.props) ? { ...node.props } : {},
    settings: isRecord(node.settings) ? { ...node.settings } : {},
    children: childNodes(node).map(normalizeNode),
  }
}

function cloneNode(node: BlockNode): BlockNode {
  return normalizeNode(node)
}

function childNodes(node: BlockNode): BlockNode[] {
  return Array.isArray(node.children) ? node.children.filter(isBlockNode) : []
}

function countBlocks(node: BlockNode): number {
  return 1 + childNodes(node).reduce((total, child) => total + countBlocks(child), 0)
}

function maxBlockDepth(node: BlockNode): number {
  const children = childNodes(node)
  return children.length === 0 ? 1 : 1 + Math.max(...children.map((child) => maxBlockDepth(child)))
}

function getFieldDocument(fieldName: string): BlockDocument | null {
  const value = props.entry?.payload[fieldName]
  return isBlockDocument(value) ? { version: 1, root: normalizeNode(value.root) } : null
}

function createDefaultDocument(): BlockDocument {
  return {
    version: 1,
    root: defaultBlock('section'),
  }
}

function createInitialDocument(): BlockDocument {
  const existingDocument = props.blockFields.map((field) => getFieldDocument(field.name)).find((document): document is BlockDocument => document !== null)
  return existingDocument ?? createDefaultDocument()
}

function defaultBlock(type: BlockType): BlockNode {
  switch (type) {
    case 'section':
      return { type, props: {}, settings: { width: 'wide', background: 'none' }, children: [] }
    case 'container':
      return { type, props: {}, settings: { width: 'wide', background: 'none' }, children: [] }
    case 'columns':
      return {
        type,
        props: { columns: 2 },
        settings: {},
        children: [defaultBlock('container'), defaultBlock('container')],
      }
    case 'heading':
      return { type, props: { text: 'New heading', level: 2 }, settings: { align: 'left' }, children: [] }
    case 'paragraph':
      return { type, props: { html: 'Start writing paragraph text.' }, settings: { align: 'left' }, children: [] }
    case 'image':
      return { type, props: { media_id: '', src: '', alt: '', caption: '' }, settings: { align: 'center' }, children: [] }
    case 'button':
      return { type, props: { label: 'Call to action', href: '' }, settings: { variant: 'primary' }, children: [] }
    case 'divider':
      return { type, props: {}, settings: {}, children: [] }
    case 'spacer':
      return { type, props: { size: 'medium' }, settings: {}, children: [] }
    case 'quote':
      return { type, props: { text: 'A short quote.', citation: '' }, settings: {}, children: [] }
    case 'list':
      return { type, props: { style: 'unordered', items: ['First item'] }, settings: {}, children: [] }
    case 'card':
      return { type, props: {}, settings: { variant: 'outlined' }, children: [defaultBlock('heading'), defaultBlock('paragraph')] }
  }
}

function pathKey(path: number[]): string {
  return path.join('.')
}

function getNode(path: number[]): BlockNode | null {
  let current: BlockNode = draftDocument.value.root
  for (const index of path) {
    const child = childNodes(current)[index]
    if (child === undefined) {
      return null
    }
    current = child
  }
  return current
}

function getParent(path: number[]): { parent: BlockNode; index: number } | null {
  if (path.length === 0) {
    return null
  }
  const parent = getNode(path.slice(0, -1))
  if (parent === null) {
    return null
  }
  return { parent, index: path[path.length - 1] }
}

function flattenNode(node: BlockNode, path: number[] = [], depth = 0): FlatNode[] {
  const current = [{ node, path, depth, key: pathKey(path) }]
  return current.concat(childNodes(node).flatMap((child, index) => flattenNode(child, [...path, index], depth + 1)))
}

function selectPath(path: number[]): void {
  selectedPath.value = [...path]
}

function mutateDraft(mutator: () => void): void {
  if (props.readOnly || props.saving) {
    return
  }

  mutator()
  draftDocument.value = { version: 1, root: normalizeNode(draftDocument.value.root) }
  if (getNode(selectedPath.value) === null) {
    selectedPath.value = []
  }
  emit('draft-change', draftDocument.value)
}

function saveDraft(): void {
  if (props.readOnly || props.saving) {
    return
  }

  emit('save', { version: 1, root: normalizeNode(draftDocument.value.root) })
}

function canContainChildren(node: BlockNode): boolean {
  return ['section', 'container', 'columns', 'card'].includes(node.type)
}

function addBlock(type: BlockType): void {
  const block = defaultBlock(type)
  mutateDraft(() => {
    const selected = getNode(selectedPath.value)
    if (selected !== null && canContainChildren(selected)) {
      selected.children.push(block)
      selectedPath.value = [...selectedPath.value, selected.children.length - 1]
      return
    }

    const parentInfo = getParent(selectedPath.value)
    if (parentInfo !== null) {
      parentInfo.parent.children.splice(parentInfo.index + 1, 0, block)
      selectedPath.value = [...selectedPath.value.slice(0, -1), parentInfo.index + 1]
      return
    }

    draftDocument.value.root.children.push(block)
    selectedPath.value = [draftDocument.value.root.children.length - 1]
  })
}


function blockNode(type: BlockType, props: Record<string, unknown> = {}, settings: Record<string, unknown> = {}, children: BlockNode[] = []): BlockNode {
  return { type, props, settings, children }
}

function patternBlocks(type: PatternType): BlockNode[] {
  switch (type) {
    case 'hero-cta':
      return [blockNode('section', {}, { width: 'full', background: 'accent' }, [blockNode('container', {}, { width: 'wide', background: 'none' }, [blockNode('heading', { text: 'Build your next launch page faster', level: 1 }, { align: 'left' }), blockNode('paragraph', { html: 'Use reusable sections to publish polished pages with trusted defaults.' }, { align: 'left' }), blockNode('button', { label: 'Start now', href: '/contact' }, { variant: 'primary' }), blockNode('image', { media_id: '', src: '/media/hero.jpg', alt: 'Hero preview', caption: '' }, { align: 'wide' })])])]
    case 'services-grid':
      return [blockNode('section', {}, { width: 'wide', background: 'muted' }, [blockNode('heading', { text: 'Services built for fast teams', level: 2 }, { align: 'left' }), blockNode('columns', { columns: 3 }, {}, [blockNode('card', {}, { variant: 'outlined' }, [blockNode('heading', { text: 'Strategy', level: 3 }, { align: 'left' }), blockNode('paragraph', { html: 'Roadmaps, positioning, and launch clarity.' }, { align: 'left' })]), blockNode('card', {}, { variant: 'outlined' }, [blockNode('heading', { text: 'Design systems', level: 3 }, { align: 'left' }), blockNode('paragraph', { html: 'Reusable UI patterns with governance.' }, { align: 'left' })]), blockNode('card', {}, { variant: 'outlined' }, [blockNode('heading', { text: 'Delivery', level: 3 }, { align: 'left' }), blockNode('paragraph', { html: 'Ship updates safely with measurable outcomes.' }, { align: 'left' })])])])]
    case 'testimonials-strip':
      return [blockNode('section', {}, { width: 'wide', background: 'none' }, [blockNode('heading', { text: 'Trusted by product teams', level: 2 }, { align: 'center' }), blockNode('columns', { columns: 3 }, {}, [blockNode('card', {}, { variant: 'elevated' }, [blockNode('quote', { text: 'We launched in half the time with cleaner handoffs.', citation: 'VP Product, Northstar' })]), blockNode('card', {}, { variant: 'elevated' }, [blockNode('quote', { text: 'Pattern sections gave us instant visual consistency.', citation: 'Design Lead, Horizon' })]), blockNode('card', {}, { variant: 'elevated' }, [blockNode('quote', { text: 'Editors now ship updates without dev bottlenecks.', citation: 'Content Ops, Atlas' })])])])]
    case 'team-grid':
      return [blockNode('section', {}, { width: 'wide', background: 'none' }, [blockNode('heading', { text: 'Meet the team', level: 2 }, { align: 'left' }), blockNode('columns', { columns: 3 }, {}, [blockNode('card', {}, { variant: 'outlined' }, [blockNode('image', { media_id: '', src: '/media/team-1.jpg', alt: 'Team member', caption: '' }, { align: 'center' }), blockNode('heading', { text: 'Alex Rivera', level: 3 }, { align: 'left' }), blockNode('paragraph', { html: 'Product strategy lead' }, { align: 'left' })]), blockNode('card', {}, { variant: 'outlined' }, [blockNode('image', { media_id: '', src: '/media/team-2.jpg', alt: 'Team member', caption: '' }, { align: 'center' }), blockNode('heading', { text: 'Morgan Lee', level: 3 }, { align: 'left' }), blockNode('paragraph', { html: 'Design systems' }, { align: 'left' })]), blockNode('card', {}, { variant: 'outlined' }, [blockNode('image', { media_id: '', src: '/media/team-3.jpg', alt: 'Team member', caption: '' }, { align: 'center' }), blockNode('heading', { text: 'Sam Patel', level: 3 }, { align: 'left' }), blockNode('paragraph', { html: 'Engineering delivery' }, { align: 'left' })])])])]
    case 'cta-banner':
      return [blockNode('section', {}, { width: 'wide', background: 'accent' }, [blockNode('container', {}, { width: 'narrow', background: 'none' }, [blockNode('heading', { text: 'Ready to accelerate publishing?', level: 2 }, { align: 'center' }), blockNode('paragraph', { html: 'Talk to our team and start with a guided setup.' }, { align: 'center' }), blockNode('button', { label: 'Book a demo', href: '/contact' }, { variant: 'primary' })])])]
  }
}

function insertPattern(type: PatternType): void {
  mutateDraft(() => {
    const blocks = patternBlocks(type).map(normalizeNode)
    const startIndex = draftDocument.value.root.children.length
    draftDocument.value.root.children.push(...blocks)
    selectedPath.value = [startIndex]
  })
}

function canMove(path: number[], direction: -1 | 1): boolean {
  const parentInfo = getParent(path)
  if (parentInfo === null) {
    return false
  }
  const nextIndex = parentInfo.index + direction
  return nextIndex >= 0 && nextIndex < childNodes(parentInfo.parent).length
}

function moveBlock(path: number[], direction: -1 | 1): void {
  if (!canMove(path, direction)) {
    return
  }

  mutateDraft(() => {
    const parentInfo = getParent(path)
    if (parentInfo === null) {
      return
    }
    const [node] = parentInfo.parent.children.splice(parentInfo.index, 1)
    parentInfo.parent.children.splice(parentInfo.index + direction, 0, node)
    selectedPath.value = [...path.slice(0, -1), parentInfo.index + direction]
  })
}

function duplicateSelectedBlock(): void {
  const parentInfo = getParent(selectedPath.value)
  const selected = selectedNode.value
  if (parentInfo === null || selected === null) {
    return
  }

  mutateDraft(() => {
    parentInfo.parent.children.splice(parentInfo.index + 1, 0, cloneNode(selected))
    selectedPath.value = [...selectedPath.value.slice(0, -1), parentInfo.index + 1]
  })
}

function deleteSelectedBlock(): void {
  const parentInfo = getParent(selectedPath.value)
  if (parentInfo === null) {
    return
  }

  mutateDraft(() => {
    parentInfo.parent.children.splice(parentInfo.index, 1)
    selectedPath.value = selectedPath.value.slice(0, -1)
  })
}

function updateProp(key: string, value: unknown): void {
  mutateDraft(() => {
    const selected = selectedNode.value
    if (selected !== null) {
      selected.props[key] = value
    }
  })
}

function updateSetting(key: string, value: unknown): void {
  mutateDraft(() => {
    const selected = selectedNode.value
    if (selected !== null) {
      selected.settings[key] = value
    }
  })
}

function updateListItems(value: string): void {
  const items = value.split('\n').map((item) => item.trim()).filter(Boolean)
  updateProp('items', items)
}

function eventValue(event: Event): string {
  const target = event.target as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | null
  return target?.value ?? ''
}

function stringFrom(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function stringProp(key: string, fallback = ''): string {
  return stringFrom(selectedNode.value?.props[key], fallback)
}

function numberProp(key: string, fallback: number): number {
  const value = selectedNode.value?.props[key]
  return typeof value === 'number' ? value : fallback
}

function stringSetting(key: string, fallback = ''): string {
  return stringFrom(selectedNode.value?.settings[key], fallback)
}

function supportsAlign(type: string): boolean {
  return ['heading', 'paragraph', 'image'].includes(type)
}

function alignOptions(type: string): string[] {
  return type === 'image' ? ['left', 'center', 'right', 'wide'] : ['left', 'center', 'right']
}

function textFromProp(node: BlockNode, key: string): string {
  return stringFrom(node.props[key])
}

function stripHtml(value: string): string {
  return value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
}

function blockLabel(node: BlockNode): string {
  switch (node.type) {
    case 'heading':
      return textFromProp(node, 'text') || 'Untitled heading'
    case 'paragraph':
      return stripHtml(textFromProp(node, 'html')) || 'Empty paragraph'
    case 'button':
      return textFromProp(node, 'label') || 'Untitled button'
    case 'image':
      return textFromProp(node, 'alt') || 'Image block'
    case 'quote':
      return textFromProp(node, 'text') || 'Quote block'
    case 'list':
      return 'List block'
    default:
      return `${node.type.charAt(0).toUpperCase()}${node.type.slice(1)} block`
  }
}

function hasText(value: unknown): boolean {
  return typeof value === 'string' && value.trim().length > 0
}

function isValidUrl(value: unknown): boolean {
  if (!hasText(value)) {
    return false
  }
  return /^(https?:\/\/|\/)/.test(String(value).trim())
}

function validateNode(node: BlockNode, key: string): ValidationItem[] {
  const issues: ValidationItem[] = []
  const addIssue = (message: string) => issues.push({ key, message })

  switch (node.type) {
    case 'heading':
      if (!hasText(node.props.text)) addIssue('Heading text is required.')
      break
    case 'paragraph':
      if (!hasText(stripHtml(stringFrom(node.props.html)))) addIssue('Paragraph text is required.')
      break
    case 'image':
      if (!hasText(node.props.alt)) addIssue('Image alt text is required.')
      if (!hasText(node.props.media_id) && !hasText(node.props.src)) addIssue('Image needs an existing media ID or image URL.')
      if (hasText(node.props.src) && !isValidUrl(node.props.src)) addIssue('Image URL must be http(s) or site-relative.')
      break
    case 'button':
      if (!hasText(node.props.label)) addIssue('Button label is required.')
      if (!isValidUrl(node.props.href)) addIssue('Button link URL is required and must be http(s) or site-relative.')
      break
    case 'quote':
      if (!hasText(node.props.text)) addIssue('Quote text is required.')
      break
    case 'list': {
      const items = Array.isArray(node.props.items) ? node.props.items.filter(hasText) : []
      if (items.length === 0) addIssue('List needs at least one item.')
      break
    }
    case 'columns':
      if (childNodes(node).length < 2) addIssue('Columns need at least two child containers.')
      break
  }

  return issues.concat(childNodes(node).flatMap((child, index) => validateNode(child, key === '' ? String(index) : `${key}.${index}`)))
}

function isAiTextTarget(node: BlockNode | null): node is BlockNode {
  return node !== null && ['heading', 'paragraph', 'button', 'quote', 'image', 'list'].includes(node.type)
}

function truncateText(value: string, limit = 220): string {
  const normalized = value.replace(/\s+/g, ' ').trim()
  return normalized.length > limit ? `${normalized.slice(0, limit - 1)}…` : normalized
}

function summarizeBlockForAi(node: BlockNode): string {
  switch (node.type) {
    case 'heading':
      return `heading: ${textFromProp(node, 'text') || 'Untitled heading'}`
    case 'paragraph':
      return `paragraph: ${stripHtml(textFromProp(node, 'html')) || 'Empty paragraph'}`
    case 'button':
      return `button: ${textFromProp(node, 'label') || 'Untitled button'} -> ${textFromProp(node, 'href') || 'no link'}`
    case 'image':
      return `image alt: ${textFromProp(node, 'alt') || 'missing alt text'}`
    case 'quote':
      return `quote: ${textFromProp(node, 'text') || 'Empty quote'}`
    case 'list': {
      const items = Array.isArray(node.props.items) ? node.props.items.filter(hasText).join('; ') : ''
      return `list: ${items || 'No list items'}`
    }
    default:
      return `${node.type} block with ${childNodes(node).length} child blocks`
  }
}

function draftOutlineForAi(): string {
  return flatNodes.value
    .slice(0, 14)
    .map((item) => `${'  '.repeat(item.depth)}- ${truncateText(summarizeBlockForAi(item.node), 120)}`)
    .join('\n')
}

function selectedBlockForAi(node: BlockNode | null): string {
  return node === null ? 'No selected block.' : truncateText(summarizeBlockForAi(node), 260)
}

function buildAiInput(action: AiAction, target: BlockNode | null): string {
  return [
    `Content type: ${props.contentType.name} (${props.contentType.slug})`,
    `Entry: ${props.entry?.slug ?? 'new draft entry'}`,
    `Action: ${action}`,
    `Selected block: ${selectedBlockForAi(target)}`,
    'Current draft outline:',
    draftOutlineForAi(),
  ].join('\n')
}

function aiInstructions(action: AiAction): string {
  switch (action) {
    case 'page-intro':
      return 'Write one concise introductory paragraph for this page. Return only the paragraph text, with no markdown and no HTML.'
    case 'rewrite-selected':
      return 'Rewrite the selected block copy while preserving intent. Return only replacement text, with no markdown and no HTML.'
    case 'suggest-cta':
      return 'Suggest one short call-to-action button label for this page. Return only the label text, no URL, no markdown, no quotes.'
  }
}

function sanitizeAiSuggestionText(value: string): string {
  return value.replace(/```[\s\S]*?```/g, '').replace(/^[\s"'“”]+|[\s"'“”]+$/g, '').trim()
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function providerUnavailableMessage(error: ApiClientError): string {
  return `Provider unavailable: ${error.detail}`
}

function aiErrorFor(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.status === 403) {
      return `Permission denied: ${error.detail}`
    }

    if (error.status === 400 || error.status === 503 || error.code?.startsWith('AI_')) {
      return providerUnavailableMessage(error)
    }

    return `Backend failure: ${error.detail}`
  }

  return `Backend failure: ${asUserMessage(error)}`
}

async function requestAiSuggestion(): Promise<void> {
  if (props.readOnly || props.saving) {
    return
  }

  const target = selectedNode.value
  if (selectedAiAction.value === 'rewrite-selected' && !isAiTextTarget(target)) {
    aiSuggestion.value = null
    aiErrorMessage.value = 'Select a heading, paragraph, button, quote, image, or list block before requesting a rewrite.'
    return
  }

  aiGenerating.value = true
  aiErrorMessage.value = null
  aiSuggestion.value = null

  try {
    const action = selectedAiAction.value
    const response = await generateAiText({
      scope: 'editor',
      input: buildAiInput(action, target),
      instructions: aiInstructions(action),
      temperature: 0.4,
      max_output_tokens: action === 'page-intro' ? 180 : 96,
    })
    const text = sanitizeAiSuggestionText(response.text)
    if (!hasText(text)) {
      throw new Error('AI returned an empty suggestion')
    }
    aiSuggestion.value = {
      action,
      targetPath: [...selectedPath.value],
      targetType: target?.type ?? 'document',
      text,
    }
  } catch (error) {
    aiErrorMessage.value = aiErrorFor(error)
  } finally {
    aiGenerating.value = false
  }
}

function applyTextSuggestion(node: BlockNode, text: string): void {
  switch (node.type) {
    case 'heading':
      node.props.text = text
      break
    case 'paragraph':
      node.props.html = escapeHtml(text)
      break
    case 'button':
      node.props.label = text
      break
    case 'image':
      node.props.alt = text
      break
    case 'quote':
      node.props.text = text
      break
    case 'list':
      node.props.items = text.split('\n').map((item) => item.trim()).filter(Boolean)
      break
  }
}

function insertAiButton(targetPath: number[], label: string): void {
  const button = blockNode('button', { label: truncateText(label, 64), href: '' }, { variant: 'primary' }, [])
  const target = getNode(targetPath)
  if (target !== null && canContainChildren(target)) {
    target.children.push(button)
    selectedPath.value = [...targetPath, target.children.length - 1]
    return
  }

  const parentInfo = getParent(targetPath)
  if (parentInfo !== null) {
    parentInfo.parent.children.splice(parentInfo.index + 1, 0, button)
    selectedPath.value = [...targetPath.slice(0, -1), parentInfo.index + 1]
    return
  }

  draftDocument.value.root.children.push(button)
  selectedPath.value = [draftDocument.value.root.children.length - 1]
}

function acceptAiSuggestion(): void {
  const suggestion = aiSuggestion.value
  if (suggestion === null) {
    return
  }

  mutateDraft(() => {
    if (suggestion.action === 'page-intro') {
      draftDocument.value.root.children.unshift(blockNode('paragraph', { html: escapeHtml(suggestion.text) }, { align: 'left' }, []))
      selectedPath.value = [0]
      return
    }

    if (suggestion.action === 'suggest-cta') {
      insertAiButton(suggestion.targetPath, suggestion.text)
      return
    }

    const target = getNode(suggestion.targetPath)
    if (target !== null && isAiTextTarget(target)) {
      applyTextSuggestion(target, suggestion.text)
      selectedPath.value = [...suggestion.targetPath]
    }
  })
  aiSuggestion.value = null
  aiErrorMessage.value = null
}

function dismissAiSuggestion(): void {
  aiSuggestion.value = null
  aiErrorMessage.value = null
}

const fieldSummaries = computed<FieldSummary[]>(() =>
  props.blockFields.map((field) => {
    const document = getFieldDocument(field.name)
    return {
      name: field.name,
      label: field.label,
      helpText: field.help_text ?? null,
      document,
      stateLabel: document === null ? 'New local draft' : 'Existing document',
    }
  }),
)

const flatNodes = computed(() => flattenNode(draftDocument.value.root))
const selectedKey = computed(() => pathKey(selectedPath.value))
const selectedNode = computed(() => getNode(selectedPath.value))
const isRootSelected = computed(() => selectedPath.value.length === 0)
const blockCount = computed(() => countBlocks(draftDocument.value.root))
const maxDepth = computed(() => maxBlockDepth(draftDocument.value.root))
const validationItems = computed(() => validateNode(draftDocument.value.root, ''))
const selectedValidationMessages = computed(() => validationItems.value.filter((item) => item.key === selectedKey.value).map((item) => item.message))
const listItemsText = computed(() => {
  const items = selectedNode.value?.props.items
  return Array.isArray(items) ? items.filter(hasText).join('\n') : ''
})
const title = computed(() => props.entry === null || props.entry === undefined ? `New ${props.contentType.name} block entry` : `Editing ${props.entry.slug}`)
const readOnly = computed(() => props.readOnly)
const saving = computed(() => props.saving)
const errorMessage = computed(() => props.errorMessage)
const editorControlsDisabled = computed(() => props.readOnly || props.saving)
const statusLabel = computed(() => props.readOnly ? 'Read-only preview' : 'Draft save enabled')
const saveDisabledReason = computed(() => props.readOnly ? 'Saving requires content entry write permission.' : undefined)
const aiActionDescription = computed(() => {
  if (selectedAiAction.value === 'page-intro') {
    return 'Generates a short introduction and inserts it at the top only after Accept.'
  }

  if (selectedAiAction.value === 'rewrite-selected') {
    const node = selectedNode.value
    return isAiTextTarget(node)
      ? `Rewrites the selected ${node.type} block only after Accept.`
      : 'Select a heading, paragraph, button, quote, image, or list block to rewrite.'
  }

  return 'Generates a CTA button label and inserts a local button only after Accept.'
})
const aiGenerateDisabled = computed(() => {
  if (editorControlsDisabled.value || aiGenerating.value) {
    return true
  }

  return selectedAiAction.value === 'rewrite-selected' && !isAiTextTarget(selectedNode.value)
})
const aiSuggestionLabel = computed(() => {
  if (aiSuggestion.value === null) {
    return ''
  }

  const action = aiActions.find((item) => item.value === aiSuggestion.value?.action)?.label ?? 'AI suggestion'
  return `${action} · target ${aiSuggestion.value.targetType}`
})
const draftSourceKey = computed(() => JSON.stringify(props.blockFields.map((field) => props.entry?.payload[field.name] ?? null)))

watch(
  () => [props.entry?.id ?? 'new', props.blockFields.map((field) => field.name).join(','), draftSourceKey.value],
  () => {
    draftDocument.value = createInitialDocument()
    selectedPath.value = []
    dismissAiSuggestion()
  },
)

const BlockPreview = defineComponent({
  name: 'BlockPreview',
  props: {
    node: { type: Object as () => BlockNode, required: true },
    path: { type: Array as () => number[], required: true },
  },
  setup(componentProps) {
    const renderChildren = () => childNodes(componentProps.node).map((child, index) => h(BlockPreview, { node: child, path: [...componentProps.path, index] }))
    const selectCurrent = () => selectPath(componentProps.path)
    const commonProps = {
      class: [
        'block-editor-shell__preview-block',
        `block-editor-shell__preview-block--${componentProps.node.type}`,
        pathKey(componentProps.path) === selectedKey.value ? 'block-editor-shell__preview-block--selected' : '',
      ],
      tabindex: 0,
      role: 'button',
      'aria-label': `Select ${componentProps.node.type} block`,
      'data-testid': `canvas-block-${componentProps.node.type}`,
      onClick: selectCurrent,
      onKeydown: (event: KeyboardEvent) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          selectCurrent()
        }
      },
    }

    return () => {
      switch (componentProps.node.type) {
        case 'heading':
          return h('div', commonProps, [h('h3', textFromProp(componentProps.node, 'text') || 'Untitled heading')])
        case 'paragraph':
          return h('div', commonProps, [h('p', stripHtml(textFromProp(componentProps.node, 'html')) || 'Empty paragraph')])
        case 'image':
          return h('figure', commonProps, [
            h('div', { class: 'block-editor-shell__image-placeholder' }, textFromProp(componentProps.node, 'src') || textFromProp(componentProps.node, 'media_id') || 'Image media not selected'),
            h('figcaption', textFromProp(componentProps.node, 'caption') || textFromProp(componentProps.node, 'alt') || 'Alt text required'),
          ])
        case 'button':
          return h('div', commonProps, [h('span', { class: 'block-editor-shell__button-preview' }, textFromProp(componentProps.node, 'label') || 'Untitled button')])
        case 'divider':
          return h('div', commonProps, [h('hr')])
        case 'spacer':
          return h('div', commonProps, [h('span', { class: 'muted' }, `Spacer · ${textFromProp(componentProps.node, 'size') || 'medium'}`)])
        case 'quote':
          return h('blockquote', commonProps, [textFromProp(componentProps.node, 'text') || 'Quote text required'])
        case 'list': {
          const items = Array.isArray(componentProps.node.props.items) ? componentProps.node.props.items.filter(hasText) : []
          const tag = componentProps.node.props.style === 'ordered' ? 'ol' : 'ul'
          return h('div', commonProps, [h(tag, items.map((item) => h('li', String(item))))])
        }
        default:
          return h('section', commonProps, [
            h('div', { class: 'block-editor-shell__preview-label' }, blockLabel(componentProps.node)),
            ...renderChildren(),
          ])
      }
    }
  },
})
</script>

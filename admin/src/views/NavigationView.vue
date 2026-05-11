<template>
  <div class='page navigation-view'>
    <div class='page__header navigation-view__header'>
      <div>
        <h1>Navigation</h1>
        <p class='muted'>Manage the public primary menu without editing theme templates.</p>
        <p class='muted'>Use the content picker for internal links and add child links to build nested menus.</p>
      </div>
      <div class='inline-actions'>
        <Button label='Refresh' icon='pi pi-refresh' severity='secondary' variant='outlined' :loading='loading' :disabled='saving' @click='loadMenu' />
        <Button label='Reset local changes' icon='pi pi-undo' severity='secondary' variant='outlined' :disabled='saving || !loaded' data-testid='navigation-reset' @click='resetLocalState' />
        <Button label='Save primary menu' icon='pi pi-save' :loading='saving' :disabled='loading || !loaded' data-testid='navigation-save' @click='saveMenu' />
      </div>
    </div>

    <Message v-if='loadErrorMessage' severity='error' :closable='false'>
      {{ loadErrorMessage }}
    </Message>
    <Message v-if='successMessage' severity='success' closable @close='successMessage = null'>
      {{ successMessage }}
    </Message>
    <Message v-if='errorMessages.length > 0' severity='error' :closable='false'>
      <ul class='navigation-view__message-list'>
        <li v-for='message in errorMessages' :key='message'>{{ message }}</li>
      </ul>
    </Message>
    <Message v-if='menuWarnings.length > 0' severity='warn' :closable='false'>
      <strong>Target warnings</strong>
      <ul class='navigation-view__message-list'>
        <li v-for='warning in menuWarnings' :key='`${warning.item_position}-${warning.item_label}`'>
          {{ warning.item_label }}: {{ warning.detail }}
        </li>
      </ul>
    </Message>

    <datalist id='navigation-content-options'>
      <option
        v-for='option in contentOptions'
        :key='option.id'
        :value='option.id'
      >
        {{ option.label }} ({{ option.content_type_slug }}/{{ option.slug }}) — {{ option.status }}
      </option>
    </datalist>

    <div v-if='loading && !loaded' class='loading-state' role='status'>Loading primary navigation…</div>

    <template v-else>
      <Card>
        <template #title>Primary menu items</template>
        <template #content>
          <div class='form-stack'>
            <div class='navigation-view__toolbar'>
              <div>
                <p class='muted'>Items save in the order shown. Child items render as nested public navigation. Disabled items remain stored but are not rendered publicly.</p>
              </div>
              <div class='inline-actions'>
                <Button label='Add internal link' icon='pi pi-file' severity='secondary' variant='outlined' data-testid='navigation-add-internal' :disabled='saving' @click='addInternalItem' />
                <Button label='Add custom URL' icon='pi pi-link' severity='secondary' variant='outlined' data-testid='navigation-add-custom' :disabled='saving' @click='addCustomItem' />
              </div>
            </div>

            <div v-if='loaded && draftItems.length === 0' class='empty-state' data-testid='navigation-empty-state'>
              <h2>No primary navigation items yet</h2>
              <p class='muted'>Add an internal content entry link or custom URL to build the public menu.</p>
            </div>

            <div v-else class='navigation-view__items' aria-label='Primary navigation items'>
              <div
                v-for='(flat, flatIndex) in flattenedItems'
                :key='flat.item.clientId'
                class='navigation-view__item'
                :data-testid='`navigation-item-${flatIndex}`'
                :style='{ marginInlineStart: `${flat.level * 1.25}rem` }'
              >
                <div class='navigation-view__item-header'>
                  <div>
                    <strong>{{ flat.item.label || `Item ${flatIndex + 1}` }}</strong>
                    <p class='muted'>{{ targetSummary(flat.item) }}</p>
                  </div>
                  <div class='navigation-view__item-tags'>
                    <Tag v-if='flat.level > 0' severity='info' :value='`Level ${flat.level + 1}`' />
                    <Tag :severity='flat.item.enabled ? `success` : `secondary`' :value='flat.item.enabled ? `Enabled` : `Disabled`' />
                    <Tag v-if='flat.item.entry_status && flat.item.entry_status !== `published`' severity='warn' :value='`Target ${flat.item.entry_status}`' />
                  </div>
                </div>

                <div class='form-grid'>
                  <div class='field'>
                    <label :for='`navigation-label-${flatIndex}`'>Label</label>
                    <input :id='`navigation-label-${flatIndex}`' v-model.trim='flat.item.label' :data-testid='`navigation-label-${flatIndex}`' :disabled='saving' />
                  </div>

                  <div class='field'>
                    <label :for='`navigation-type-${flatIndex}`'>Link type</label>
                    <select :id='`navigation-type-${flatIndex}`' v-model='flat.item.link_type' :data-testid='`navigation-type-${flatIndex}`' :disabled='saving' @change='normalizeTargetShape(flat.item)'>
                      <option value='content_entry'>Internal content entry</option>
                      <option value='custom_url'>Custom URL</option>
                    </select>
                  </div>

                  <div v-if='flat.item.link_type === `content_entry`' class='field field--full'>
                    <label :for='`navigation-entry-${flatIndex}`'>Content entry</label>
                    <input :id='`navigation-entry-${flatIndex}`' v-model.trim='flat.item.content_entry_id' :data-testid='`navigation-entry-${flatIndex}`' :disabled='saving' list='navigation-content-options' placeholder='Search or paste a content entry ID' />
                    <small class='muted'>{{ contentPickerHelp(flat.item) }}</small>
                  </div>

                  <div v-else class='field field--full'>
                    <label :for='`navigation-url-${flatIndex}`'>Custom URL</label>
                    <input :id='`navigation-url-${flatIndex}`' v-model.trim='flat.item.url' :data-testid='`navigation-url-${flatIndex}`' :disabled='saving' placeholder='/about or https://example.com' />
                    <small class='muted'>Backend validation allows relative paths and http(s) URLs only.</small>
                  </div>

                  <div class='field field--full'>
                    <label class='field__checkbox-row'>
                      <input type='checkbox' v-model='flat.item.enabled' :data-testid='`navigation-enabled-${flatIndex}`' :disabled='saving' />
                      Enabled in public navigation
                    </label>
                  </div>
                </div>

                <div class='inline-actions navigation-view__item-actions'>
                  <Button label='Add child internal' icon='pi pi-file-plus' severity='secondary' variant='outlined' :disabled='saving || flat.level >= maxNestedLevel' :data-testid='`navigation-add-child-internal-${flatIndex}`' @click='addInternalChild(flat.item)' />
                  <Button label='Add child URL' icon='pi pi-plus-circle' severity='secondary' variant='outlined' :disabled='saving || flat.level >= maxNestedLevel' :data-testid='`navigation-add-child-custom-${flatIndex}`' @click='addCustomChild(flat.item)' />
                  <Button label='Move up' icon='pi pi-arrow-up' severity='secondary' variant='outlined' :disabled='saving || flat.index === 0' :data-testid='`navigation-move-up-${flatIndex}`' @click='moveItem(flat.siblings, flat.index, -1)' />
                  <Button label='Move down' icon='pi pi-arrow-down' severity='secondary' variant='outlined' :disabled='saving || flat.index === flat.siblings.length - 1' :data-testid='`navigation-move-down-${flatIndex}`' @click='moveItem(flat.siblings, flat.index, 1)' />
                  <Button label='Remove' icon='pi pi-trash' severity='danger' variant='outlined' :disabled='saving' :data-testid='`navigation-remove-${flatIndex}`' @click='removeItem(flat.siblings, flat.index)' />
                </div>
              </div>
            </div>
          </div>
        </template>
      </Card>
    </template>
  </div>
</template>

<script setup lang='ts'>
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import { ApiClientError, asUserMessage } from '@/api/errors'
import {
  getPrimaryNavigationMenu,
  listNavigationContentOptions,
  replacePrimaryNavigationMenu,
} from '@/api/navigation'
import type {
  NavigationContentOption,
  NavigationLinkType,
  NavigationMenuItemRequest,
  NavigationMenuItemResponse,
  NavigationWarningResponse,
} from '@/api/navigation'

interface EditableNavigationItem {
  clientId: string
  label: string
  link_type: NavigationLinkType
  content_entry_id: string
  url: string
  enabled: boolean
  entry_status: string | null
  href: string | null
  children: EditableNavigationItem[]
}

interface FlattenedNavigationItem {
  item: EditableNavigationItem
  siblings: EditableNavigationItem[]
  index: number
  level: number
}

const maxNestedLevel = 2
const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const draftItems = ref<EditableNavigationItem[]>([])
const savedItems = ref<EditableNavigationItem[]>([])
const contentOptions = ref<NavigationContentOption[]>([])
const menuWarnings = ref<NavigationWarningResponse[]>([])
const loadErrorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)
const errorMessages = ref<string[]>([])
const hasItems = computed(() => draftItems.value.length > 0)
const flattenedItems = computed(() => flattenItems(draftItems.value))
let nextClientId = 1

onMounted(() => {
  void loadMenu()
})

async function loadMenu(): Promise<void> {
  loading.value = true
  loadErrorMessage.value = null
  errorMessages.value = []
  successMessage.value = null

  try {
    const [response, options] = await Promise.all([
      getPrimaryNavigationMenu(),
      listNavigationContentOptions(),
    ])
    contentOptions.value = options.items
    applyMenuSnapshot(response.items, response.warnings)
    loaded.value = true
  } catch (error) {
    loadErrorMessage.value = formatApiError(error)[0] ?? 'Unable to load primary navigation.'
  } finally {
    loading.value = false
  }
}

function applyMenuSnapshot(
  items: NavigationMenuItemResponse[],
  warnings: NavigationWarningResponse[],
): void {
  draftItems.value = sortResponseItems(items).map(toEditableItem)
  savedItems.value = cloneItems(draftItems.value)
  menuWarnings.value = warnings
}

function sortResponseItems(items: NavigationMenuItemResponse[]): NavigationMenuItemResponse[] {
  return [...items]
    .sort((left, right) => left.position - right.position)
    .map((item) => ({ ...item, children: sortResponseItems(item.children ?? []) }))
}

function toEditableItem(item: NavigationMenuItemResponse): EditableNavigationItem {
  return {
    clientId: nextClientKey(),
    label: item.label,
    link_type: item.link_type,
    content_entry_id: item.content_entry_id ?? '',
    url: item.url ?? '',
    enabled: item.enabled,
    entry_status: item.entry_status,
    href: item.href,
    children: sortResponseItems(item.children ?? []).map(toEditableItem),
  }
}

function nextClientKey(): string {
  const key = `navigation-item-${nextClientId}`
  nextClientId += 1
  return key
}

function cloneItems(items: EditableNavigationItem[]): EditableNavigationItem[] {
  return items.map((item) => ({
    ...item,
    clientId: nextClientKey(),
    children: cloneItems(item.children),
  }))
}

function createInternalItem(label = 'Internal link'): EditableNavigationItem {
  return {
    clientId: nextClientKey(),
    label,
    link_type: 'content_entry',
    content_entry_id: '',
    url: '',
    enabled: true,
    entry_status: null,
    href: null,
    children: [],
  }
}

function createCustomItem(label = 'Custom link'): EditableNavigationItem {
  return {
    clientId: nextClientKey(),
    label,
    link_type: 'custom_url',
    content_entry_id: '',
    url: '/',
    enabled: true,
    entry_status: null,
    href: null,
    children: [],
  }
}

function addInternalItem(): void {
  draftItems.value.push(createInternalItem())
}

function addCustomItem(): void {
  draftItems.value.push(createCustomItem())
}

function addInternalChild(parent: EditableNavigationItem): void {
  parent.children.push(createInternalItem('Child internal link'))
}

function addCustomChild(parent: EditableNavigationItem): void {
  parent.children.push(createCustomItem('Child custom link'))
}

function normalizeTargetShape(item: EditableNavigationItem): void {
  item.entry_status = null
  item.href = null
  if (item.link_type === 'content_entry') {
    item.url = ''
    return
  }
  item.content_entry_id = ''
  if (!item.url) {
    item.url = '/'
  }
}

function moveItem(siblings: EditableNavigationItem[], index: number, direction: -1 | 1): void {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= siblings.length) {
    return
  }

  const [item] = siblings.splice(index, 1)
  siblings.splice(targetIndex, 0, item)
}

function removeItem(siblings: EditableNavigationItem[], index: number): void {
  siblings.splice(index, 1)
}

function resetLocalState(): void {
  draftItems.value = cloneItems(savedItems.value)
  errorMessages.value = []
  successMessage.value = null
}

async function saveMenu(): Promise<void> {
  saving.value = true
  errorMessages.value = []
  successMessage.value = null

  try {
    const response = await replacePrimaryNavigationMenu({ items: draftItems.value.map(toRequestItem) })
    applyMenuSnapshot(response.items, response.warnings)
    successMessage.value = hasItems.value ? 'Primary navigation menu saved.' : 'Primary navigation menu cleared.'
    loaded.value = true
  } catch (error) {
    errorMessages.value = formatApiError(error)
  } finally {
    saving.value = false
  }
}

function toRequestItem(item: EditableNavigationItem): NavigationMenuItemRequest {
  const payload: NavigationMenuItemRequest = {
    label: item.label,
    link_type: item.link_type,
    enabled: item.enabled,
    children: item.children.map(toRequestItem),
  }

  if (item.link_type === 'content_entry') {
    payload.content_entry_id = item.content_entry_id.trim() || null
    return payload
  }

  payload.url = item.url.trim() || null
  return payload
}

function flattenItems(
  items: EditableNavigationItem[],
  level = 0,
): FlattenedNavigationItem[] {
  return items.flatMap((item, index) => [
    { item, siblings: items, index, level },
    ...flattenItems(item.children, level + 1),
  ])
}

function findContentOption(entryId: string): NavigationContentOption | null {
  return contentOptions.value.find((option) => option.id === entryId) ?? null
}

function targetSummary(item: EditableNavigationItem): string {
  if (item.link_type === 'content_entry') {
    const option = findContentOption(item.content_entry_id)
    if (option) {
      return `${option.label} (${option.content_type_slug}/${option.slug})`
    }
    return item.content_entry_id ? `Internal entry ${item.content_entry_id}` : 'Internal entry target not selected'
  }
  return item.url ? `Custom URL ${item.url}` : 'Custom URL not set'
}

function contentPickerHelp(item: EditableNavigationItem): string {
  const option = findContentOption(item.content_entry_id)
  if (option) {
    return `Selected ${option.status} ${option.content_type_slug} at ${option.href}.`
  }
  return 'Search available entries or paste a content entry UUID.'
}

function formatApiError(error: unknown): string[] {
  if (error instanceof ApiClientError) {
    const detail = error.detail as unknown
    if (Array.isArray(detail)) {
      return detail.map(formatValidationIssue)
    }
    return [error.detail]
  }

  return [asUserMessage(error)]
}

function formatValidationIssue(issue: unknown): string {
  if (typeof issue === 'object' && issue !== null) {
    const record = issue as Record<string, unknown>
    const message = typeof record.msg === 'string' ? record.msg : JSON.stringify(record)
    const location = Array.isArray(record.loc) ? record.loc.join('.') : null
    return location ? `${location}: ${message}` : message
  }
  return String(issue)
}
</script>

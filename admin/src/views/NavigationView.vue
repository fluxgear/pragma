<template>
  <div class='page navigation-view'>
    <div class='page__header navigation-view__header'>
      <div>
        <h1>Navigation</h1>
        <p class='muted'>Manage the public primary menu without editing theme templates.</p>
        <p class='muted'>This editor supports a single-level primary menu only. Nested menu items are not implemented in this C6 slice.</p>
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
      <strong>Draft target warnings</strong>
      <ul class='navigation-view__message-list'>
        <li v-for='warning in menuWarnings' :key='`${warning.item_position}-${warning.item_label}`'>
          {{ warning.item_label }}: {{ warning.detail }}
        </li>
      </ul>
    </Message>

    <div v-if='loading && !loaded' class='loading-state' role='status'>Loading primary navigation…</div>

    <template v-else>
      <Card>
        <template #title>Primary menu items</template>
        <template #content>
          <div class='form-stack'>
            <div class='navigation-view__toolbar'>
              <div>
                <p class='muted'>Items save in the order shown. Disabled items remain stored but are not rendered publicly.</p>
              </div>
              <div class='inline-actions'>
                <Button label='Add internal link' icon='pi pi-file' severity='secondary' variant='outlined' data-testid='navigation-add-internal' :disabled='saving' @click='addInternalItem' />
                <Button label='Add custom URL' icon='pi pi-link' severity='secondary' variant='outlined' data-testid='navigation-add-custom' :disabled='saving' @click='addCustomItem' />
              </div>
            </div>

            <div v-if='loaded && draftItems.length === 0' class='empty-state' data-testid='navigation-empty-state'>
              <h2>No primary navigation items yet</h2>
              <p class='muted'>Add an internal content entry link or custom URL to build the single-level public menu.</p>
            </div>

            <div v-else class='navigation-view__items' aria-label='Primary navigation items'>
              <div
                v-for='(item, index) in draftItems'
                :key='item.clientId'
                class='navigation-view__item'
                :data-testid='`navigation-item-${index}`'
              >
                <div class='navigation-view__item-header'>
                  <div>
                    <strong>{{ item.label || `Item ${index + 1}` }}</strong>
                    <p class='muted'>{{ targetSummary(item) }}</p>
                  </div>
                  <div class='navigation-view__item-tags'>
                    <Tag :severity='item.enabled ? `success` : `secondary`' :value='item.enabled ? `Enabled` : `Disabled`' />
                    <Tag v-if='item.entry_status && item.entry_status !== `published`' severity='warn' :value='`Target ${item.entry_status}`' />
                  </div>
                </div>

                <div class='form-grid'>
                  <div class='field'>
                    <label :for='`navigation-label-${index}`'>Label</label>
                    <input :id='`navigation-label-${index}`' v-model.trim='item.label' :data-testid='`navigation-label-${index}`' :disabled='saving' />
                  </div>

                  <div class='field'>
                    <label :for='`navigation-type-${index}`'>Link type</label>
                    <select :id='`navigation-type-${index}`' v-model='item.link_type' :data-testid='`navigation-type-${index}`' :disabled='saving' @change='normalizeTargetShape(item)'>
                      <option value='content_entry'>Internal content entry</option>
                      <option value='custom_url'>Custom URL</option>
                    </select>
                  </div>

                  <div v-if='item.link_type === `content_entry`' class='field field--full'>
                    <label :for='`navigation-entry-${index}`'>Content entry ID</label>
                    <input :id='`navigation-entry-${index}`' v-model.trim='item.content_entry_id' :data-testid='`navigation-entry-${index}`' :disabled='saving' placeholder='UUID of the content entry' />
                    <small class='muted'>Internal links point at a content entry and warn if the backend reports a draft or archived target.</small>
                  </div>

                  <div v-else class='field field--full'>
                    <label :for='`navigation-url-${index}`'>Custom URL</label>
                    <input :id='`navigation-url-${index}`' v-model.trim='item.url' :data-testid='`navigation-url-${index}`' :disabled='saving' placeholder='/about or https://example.com' />
                    <small class='muted'>Backend validation allows relative paths and http(s) URLs only.</small>
                  </div>

                  <div class='field field--full'>
                    <label class='field__checkbox-row'>
                      <input type='checkbox' v-model='item.enabled' :data-testid='`navigation-enabled-${index}`' :disabled='saving' />
                      Enabled in public navigation
                    </label>
                  </div>
                </div>

                <div class='inline-actions navigation-view__item-actions'>
                  <Button label='Move up' icon='pi pi-arrow-up' severity='secondary' variant='outlined' :disabled='saving || index === 0' :data-testid='`navigation-move-up-${index}`' @click='moveItem(index, -1)' />
                  <Button label='Move down' icon='pi pi-arrow-down' severity='secondary' variant='outlined' :disabled='saving || index === draftItems.length - 1' :data-testid='`navigation-move-down-${index}`' @click='moveItem(index, 1)' />
                  <Button label='Remove' icon='pi pi-trash' severity='danger' variant='outlined' :disabled='saving' :data-testid='`navigation-remove-${index}`' @click='removeItem(index)' />
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
import { getPrimaryNavigationMenu, replacePrimaryNavigationMenu } from '@/api/navigation'
import type {
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
}

const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const draftItems = ref<EditableNavigationItem[]>([])
const savedItems = ref<EditableNavigationItem[]>([])
const menuWarnings = ref<NavigationWarningResponse[]>([])
const loadErrorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)
const errorMessages = ref<string[]>([])
const hasItems = computed(() => draftItems.value.length > 0)
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
    const response = await getPrimaryNavigationMenu()
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
  const sortedItems = [...items].sort((left, right) => left.position - right.position)
  draftItems.value = sortedItems.map(toEditableItem)
  savedItems.value = cloneItems(draftItems.value)
  menuWarnings.value = warnings
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
  }
}

function nextClientKey(): string {
  const key = `navigation-item-${nextClientId}`
  nextClientId += 1
  return key
}

function cloneItems(items: EditableNavigationItem[]): EditableNavigationItem[] {
  return items.map((item) => ({ ...item, clientId: nextClientKey() }))
}

function addInternalItem(): void {
  draftItems.value.push({
    clientId: nextClientKey(),
    label: 'Internal link',
    link_type: 'content_entry',
    content_entry_id: '',
    url: '',
    enabled: true,
    entry_status: null,
    href: null,
  })
}

function addCustomItem(): void {
  draftItems.value.push({
    clientId: nextClientKey(),
    label: 'Custom link',
    link_type: 'custom_url',
    content_entry_id: '',
    url: '/',
    enabled: true,
    entry_status: null,
    href: null,
  })
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

function moveItem(index: number, direction: -1 | 1): void {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= draftItems.value.length) {
    return
  }

  const nextItems = [...draftItems.value]
  const [item] = nextItems.splice(index, 1)
  nextItems.splice(targetIndex, 0, item)
  draftItems.value = nextItems
}

function removeItem(index: number): void {
  draftItems.value.splice(index, 1)
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
  }

  if (item.link_type === 'content_entry') {
    payload.content_entry_id = item.content_entry_id.trim() || null
    return payload
  }

  payload.url = item.url.trim() || null
  return payload
}

function targetSummary(item: EditableNavigationItem): string {
  if (item.link_type === 'content_entry') {
    return item.content_entry_id ? `Internal entry ${item.content_entry_id}` : 'Internal entry target not selected'
  }
  return item.url ? `Custom URL ${item.url}` : 'Custom URL not set'
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

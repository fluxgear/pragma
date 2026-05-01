<template>
  <div class="page content-workspace">
    <div class="page__header content-workspace__header">
      <div>
        <h1>Content entries</h1>
        <p class="muted">
          Rich-text fields use the Pragma HTML contract backed by TipTap 2 and the backend content engine.
        </p>
      </div>
      <div class="inline-actions">
        <Button
          label="Refresh"
          icon="pi pi-refresh"
          severity="secondary"
          variant="outlined"
          :loading="contentTypesLoading || entriesLoading"
          @click="refreshWorkspace"
        />
        <Button
          label="New entry"
          icon="pi pi-plus"
          :disabled="selectedContentType === null || !canWriteContentEntries"
          :title="newEntryDisabledReason"
          @click="openCreateDialog"
        />
      </div>
    </div>

    <Message v-if="pageErrorMessage" severity="error" :closable="false">
      {{ pageErrorMessage }}
    </Message>
    <Message v-if="!canWriteContentEntries" severity="info" :closable="false">
      You have read-only access to content entries. New and edit actions are disabled.
    </Message>
    <Message v-else-if="!canPublishContentEntries" severity="info" :closable="false">
      Publishing entries requires the content.entries.publish permission.
    </Message>

    <Card>
      <template #title>Content type</template>
      <template #content>
        <div v-if="contentTypes.length === 0" class="form-stack">
          <Message severity="warn" :closable="false">
            No content types are configured yet. Create a content type through the content API first, then return here to author entries.
          </Message>
        </div>
        <div v-else class="form-stack">
          <div class="form-grid">
            <div class="field">
              <label for="content-type-select">Select content type</label>
              <Select
                id="content-type-select"
                v-model="selectedContentTypeId"
                :options="contentTypeOptions"
                optionLabel="label"
                optionValue="value"
                :disabled="contentTypesLoading"
              />
            </div>
          </div>
          <div class="inline-actions">
            <span class="muted" data-testid="content-types-pagination-summary">
              Content types {{ contentTypesRangeLabel }}
            </span>
            <Button
              type="button"
              label="Previous"
              severity="secondary"
              variant="outlined"
              size="small"
              data-testid="content-types-previous"
              :disabled="!hasPreviousContentTypesPage || contentTypesLoading"
              @click="goToPreviousContentTypesPage"
            />
            <Button
              type="button"
              label="Next"
              severity="secondary"
              variant="outlined"
              size="small"
              data-testid="content-types-next"
              :disabled="!hasNextContentTypesPage || contentTypesLoading"
              @click="goToNextContentTypesPage"
            />
          </div>
        </div>
      </template>
    </Card>

    <Card v-if="selectedContentType !== null">
      <template #title>{{ selectedContentType.name }}</template>
      <template #content>
        <Message v-if="selectedContentType.description" severity="info" :closable="false">
          {{ selectedContentType.description }}
        </Message>

        <div class="content-workspace__field-summary">
          <Tag
            v-for="fieldDefinition in selectedContentType.field_definitions"
            :key="fieldDefinition.name"
            :severity="fieldDefinition.kind === 'rich_text' ? 'info' : 'secondary'"
            :value="`${fieldDefinition.label} · ${fieldDefinition.kind}`"
          />
        </div>

        <DataTable
          :value="entries"
          dataKey="id"
          :loading="entriesLoading"
          responsiveLayout="scroll"
          class="content-workspace__table"
        >
          <Column header="Title">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <strong>{{ getContentEntryDisplayTitle(slotProps.data) }}</strong>
                <span class="muted code-chip">{{ slotProps.data.slug }}</span>
              </div>
            </template>
          </Column>

          <Column field="status" header="Status">
            <template #body="slotProps">
              <Tag :severity="statusSeverity(slotProps.data.status)" :value="slotProps.data.status" />
            </template>
          </Column>

          <Column field="updated_at" header="Updated">
            <template #body="slotProps">
              {{ formatTimestamp(slotProps.data.updated_at) }}
            </template>
          </Column>

          <Column header="Actions" style="width: 8rem;">
            <template #body="slotProps">
              <Button
                type="button"
                label="Edit"
                icon="pi pi-pencil"
                size="small"
                severity="secondary"
                variant="outlined"
                data-testid="entry-edit"
                :disabled="!canEditEntry(slotProps.data)"
                :title="editDisabledReason(slotProps.data)"
                @click="openEditDialog(slotProps.data)"
              />
            </template>
          </Column>

          <template #empty>
            <div class="content-workspace__empty-state muted">
              No entries exist for this content type yet.
            </div>
          </template>
        </DataTable>

        <div class="inline-actions">
          <span class="muted" data-testid="entries-pagination-summary">
            Entries {{ entriesRangeLabel }}
          </span>
          <Button
            type="button"
            label="Previous"
            severity="secondary"
            variant="outlined"
            size="small"
            data-testid="entries-previous"
            :disabled="!hasPreviousEntriesPage || entriesLoading"
            @click="goToPreviousEntriesPage"
          />
          <Button
            type="button"
            label="Next"
            severity="secondary"
            variant="outlined"
            size="small"
            data-testid="entries-next"
            :disabled="!hasNextEntriesPage || entriesLoading"
            @click="goToNextEntriesPage"
          />
        </div>
      </template>
    </Card>

    <Dialog
      v-model:visible="dialogVisible"
      modal
      :dismissableMask="!submitting"
      :draggable="false"
      :header="dialogTitle"
      :style="{ width: 'min(72rem, 95vw)' }"
    >
      <ContentEntryForm
        v-if="selectedContentType !== null"
        :content-type="selectedContentType"
        :entry="editingEntry"
        :error-message="dialogErrorMessage"
        :submitting="submitting"
        :read-only="!canSaveDialogEntry"
        :can-publish="canPublishContentEntries"
        @submit="saveEntry"
      />
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

import {
  createContentEntry,
  listContentEntries,
  listContentTypes,
  updateContentEntry,
} from '@/api/content'
import { asUserMessage } from '@/api/errors'
import type {
  ContentEntryResponse,
  ContentEntryStatus,
  ContentTypeResponse,
  RealtimeEventEnvelope,
} from '@/api/types'
import ContentEntryForm from '@/components/content/ContentEntryForm.vue'
import { getContentEntryDisplayTitle } from '@/features/content/form'
import { useAuthStore } from '@/stores/auth'
import { useRealtimeStore } from '@/stores/realtime'

const CONTENT_PAGE_SIZE = 50
const CONTENT_TYPE_ORDER_BY = 'updated_at'
const CONTENT_ENTRY_ORDER_BY = 'updated_at'

const authStore = useAuthStore()
const realtimeStore = useRealtimeStore()

const contentTypes = ref<ContentTypeResponse[]>([])
const entries = ref<ContentEntryResponse[]>([])
const selectedContentTypeId = ref<string | null>(null)
const contentTypesLoading = ref(false)
const entriesLoading = ref(false)
const contentTypesTotal = ref(0)
const contentTypesLimit = ref(CONTENT_PAGE_SIZE)
const contentTypesOffset = ref(0)
const entriesTotal = ref(0)
const entriesLimit = ref(CONTENT_PAGE_SIZE)
const entriesOffset = ref(0)
const dialogVisible = ref(false)
const editingEntry = ref<ContentEntryResponse | null>(null)
const pageErrorMessage = ref<string | null>(null)
const dialogErrorMessage = ref<string | null>(null)
const submitting = ref(false)

let unsubscribeRealtime: (() => void) | null = null
let unsubscribeResync: (() => void) | null = null

const contentTypeOptions = computed(() =>
  contentTypes.value.map((contentType) => ({
    label: contentType.name,
    value: contentType.id,
  })),
)

const selectedContentType = computed(
  () => contentTypes.value.find((contentType) => contentType.id === selectedContentTypeId.value) ?? null,
)

const dialogTitle = computed(() => (editingEntry.value === null ? 'Create content entry' : 'Edit content entry'))
const canWriteContentEntries = computed(() => authStore.hasPermission('content.entries.write'))
const canPublishContentEntries = computed(() => authStore.hasPermission('content.entries.publish'))
const newEntryDisabledReason = computed(() => {
  if (selectedContentType.value === null) {
    return 'Select a content type before creating an entry.'
  }
  return canWriteContentEntries.value ? undefined : 'Requires content.entries.write.'
})
const contentTypesRangeLabel = computed(() => paginationRangeLabel(
  contentTypesOffset.value,
  contentTypes.value.length,
  contentTypesTotal.value,
))
const entriesRangeLabel = computed(() => paginationRangeLabel(
  entriesOffset.value,
  entries.value.length,
  entriesTotal.value,
))
const hasPreviousContentTypesPage = computed(() => contentTypesOffset.value > 0)
const hasNextContentTypesPage = computed(
  () => contentTypesOffset.value + contentTypes.value.length < contentTypesTotal.value,
)
const hasPreviousEntriesPage = computed(() => entriesOffset.value > 0)
const hasNextEntriesPage = computed(() => entriesOffset.value + entries.value.length < entriesTotal.value)
const canSaveDialogEntry = computed(() => {
  if (!canWriteContentEntries.value) {
    return false
  }
  return editingEntry.value === null || editingEntry.value.status !== 'published' || canPublishContentEntries.value
})

function paginationRangeLabel(offset: number, itemCount: number, total: number): string {
  if (total === 0 || itemCount === 0) {
    return '0 of 0'
  }

  return `${offset + 1}-${offset + itemCount} of ${total}`
}

async function loadContentTypes(): Promise<void> {
  contentTypesLoading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listContentTypes({
      limit: contentTypesLimit.value,
      offset: contentTypesOffset.value,
      order_by: CONTENT_TYPE_ORDER_BY,
    })
    contentTypes.value = response.items
    contentTypesTotal.value = response.total
    contentTypesLimit.value = response.limit
    contentTypesOffset.value = response.offset

    if (response.items.length === 0) {
      selectedContentTypeId.value = null
      entries.value = []
      entriesTotal.value = 0
      entriesOffset.value = 0
      return
    }

    const hasSelectedContentType = response.items.some(
      (contentType) => contentType.id === selectedContentTypeId.value,
    )

    if (!hasSelectedContentType) {
      selectedContentTypeId.value = response.items[0].id
    }
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  } finally {
    contentTypesLoading.value = false
  }
}

async function loadEntries(): Promise<void> {
  if (selectedContentTypeId.value === null) {
    entries.value = []
    entriesTotal.value = 0
    entriesOffset.value = 0
    return
  }

  entriesLoading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listContentEntries({
      content_type_id: selectedContentTypeId.value,
      limit: entriesLimit.value,
      offset: entriesOffset.value,
      order_by: CONTENT_ENTRY_ORDER_BY,
    })
    entries.value = response.items
    entriesTotal.value = response.total
    entriesLimit.value = response.limit
    entriesOffset.value = response.offset
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
    entries.value = []
    entriesTotal.value = 0
  } finally {
    entriesLoading.value = false
  }
}

async function refreshWorkspace(): Promise<void> {
  await loadContentTypes()
  if (selectedContentTypeId.value !== null) {
    await loadEntries()
  }
}

async function goToPreviousContentTypesPage(): Promise<void> {
  if (!hasPreviousContentTypesPage.value) {
    return
  }

  contentTypesOffset.value = Math.max(0, contentTypesOffset.value - contentTypesLimit.value)
  await loadContentTypes()
}

async function goToNextContentTypesPage(): Promise<void> {
  if (!hasNextContentTypesPage.value) {
    return
  }

  contentTypesOffset.value += contentTypesLimit.value
  await loadContentTypes()
}

async function goToPreviousEntriesPage(): Promise<void> {
  if (!hasPreviousEntriesPage.value) {
    return
  }

  entriesOffset.value = Math.max(0, entriesOffset.value - entriesLimit.value)
  await loadEntries()
}

async function goToNextEntriesPage(): Promise<void> {
  if (!hasNextEntriesPage.value) {
    return
  }

  entriesOffset.value += entriesLimit.value
  await loadEntries()
}

function openCreateDialog(): void {
  if (selectedContentType.value === null || !canWriteContentEntries.value) {
    return
  }

  editingEntry.value = null
  dialogErrorMessage.value = null
  dialogVisible.value = true
}

function canEditEntry(entry: ContentEntryResponse): boolean {
  if (!canWriteContentEntries.value) {
    return false
  }

  return entry.status !== 'published' || canPublishContentEntries.value
}

function editDisabledReason(entry: ContentEntryResponse): string | undefined {
  if (!canWriteContentEntries.value) {
    return 'Requires content.entries.write.'
  }

  if (entry.status === 'published' && !canPublishContentEntries.value) {
    return 'Published entries require content.entries.publish.'
  }

  return undefined
}

function openEditDialog(entry: ContentEntryResponse): void {
  if (!canEditEntry(entry)) {
    return
  }

  editingEntry.value = entry
  dialogErrorMessage.value = null
  dialogVisible.value = true
}

async function saveEntry(payload: {
  slug: string | null
  status: ContentEntryStatus
  payload: Record<string, unknown>
}): Promise<void> {
  if (selectedContentType.value === null) {
    return
  }

  if (!canSaveDialogEntry.value) {
    dialogErrorMessage.value = 'You do not have permission to save this content entry.'
    return
  }

  if (payload.status === 'published' && !canPublishContentEntries.value) {
    dialogErrorMessage.value = 'Publishing entries requires the content.entries.publish permission.'
    return
  }

  dialogErrorMessage.value = null
  submitting.value = true

  try {
    if (editingEntry.value === null) {
      await createContentEntry({
        content_type_id: selectedContentType.value.id,
        slug: payload.slug,
        status: payload.status,
        payload: payload.payload,
      })
    } else {
      await updateContentEntry(editingEntry.value.id, payload)
    }

    dialogVisible.value = false
    editingEntry.value = null
    await loadEntries()
  } catch (error) {
    dialogErrorMessage.value = asUserMessage(error)
  } finally {
    submitting.value = false
  }
}

function statusSeverity(status: ContentEntryStatus): 'contrast' | 'info' | 'success' | 'warn' {
  switch (status) {
    case 'published':
      return 'success'
    case 'archived':
      return 'warn'
    default:
      return 'contrast'
  }
}

function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function eventMatchesSelectedContentType(event: RealtimeEventEnvelope): boolean {
  if (selectedContentTypeId.value === null) {
    return false
  }

  const contentTypeId = event.data.content_type_id
  if (typeof contentTypeId === 'string' && contentTypeId === selectedContentTypeId.value) {
    return true
  }

  const selectedSlug = selectedContentType.value?.slug
  const contentTypeSlug = event.data.content_type_slug
  return typeof selectedSlug === 'string' && typeof contentTypeSlug === 'string' && selectedSlug === contentTypeSlug
}

function handleRealtimeEvent(event: RealtimeEventEnvelope): void {
  if (
    (event.type === 'content.entry.created'
      || event.type === 'content.entry.updated'
      || event.type === 'content.entry.deleted')
    && eventMatchesSelectedContentType(event)
  ) {
    void loadEntries()
  }
}

function handleRealtimeResync(): void {
  void refreshWorkspace()
}

watch(selectedContentTypeId, async () => {
  entriesOffset.value = 0
  await loadEntries()
})

onMounted(async () => {
  await loadContentTypes()
  unsubscribeRealtime = realtimeStore.subscribe(handleRealtimeEvent)
  unsubscribeResync = realtimeStore.subscribeResync(handleRealtimeResync)
})

onUnmounted(() => {
  unsubscribeRealtime?.()
  unsubscribeResync?.()
  unsubscribeRealtime = null
  unsubscribeResync = null
})
</script>

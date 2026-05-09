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
          @click="openCreateEntry"
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
            <span v-if="canReadContentTypes">
              No content models exist yet. Create a content model before authoring entries.
            </span>
            <span v-else>
              Content entries need a content model before authors can create entries. Ask an administrator with content model access to create one.
            </span>
          </Message>
          <div v-if="canReadContentTypes" class="inline-actions">
            <Button
              type="button"
              label="Open Content Models"
              icon="pi pi-sitemap"
              data-testid="open-content-models"
              @click="navigateToContentModels"
            />
          </div>
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

          <Column header="Version">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <span>v{{ slotProps.data.version }}</span>
                <span class="muted">Revision {{ slotProps.data.revision_number ?? 'none' }}</span>
              </div>
            </template>
          </Column>

          <Column field="updated_at" header="Updated">
            <template #body="slotProps">
              {{ formatTimestamp(slotProps.data.updated_at) }}
            </template>
          </Column>

          <Column header="Actions" style="width: 14rem;">
            <template #body="slotProps">
              <div class="inline-actions">
                <Button
                  type="button"
                  :label="selectedContentTypeHasBlockDocumentFields ? 'Open editor' : 'Edit'"
                  icon="pi pi-pencil"
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  data-testid="entry-edit"
                  :disabled="!canEditEntry(slotProps.data)"
                  :title="editDisabledReason(slotProps.data)"
                  @click="openEditDialog(slotProps.data)"
                />
                <Button
                  type="button"
                  label="Workflow"
                  icon="pi pi-history"
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  data-testid="entry-workflow"
                  @click="selectWorkflowEntry(slotProps.data)"
                />
              </div>
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

        <Card v-if="selectedWorkflowEntry !== null" class="content-workspace__workflow-card">
          <template #title>Workflow controls</template>
          <template #content>
            <div class="content-workspace__workflow-grid">
              <PublishingPanel
                :entry="selectedWorkflowEntry"
                :can-publish="canPublishContentEntries"
                :can-preview="canPreviewContentEntries"
                :publishing-action="publishingAction"
                :preview-loading="previewLoading"
                :preview-url="previewUrl"
                :error-message="workflowErrorMessage"
                @preview="createAndOpenPreview"
                @publish="publishSelectedEntry"
                @unpublish="unpublishSelectedEntry"
              />
              <RevisionPanel
                :entry="selectedWorkflowEntry"
                :revisions="entryRevisions"
                :loading="revisionsLoading"
                :can-restore="canPublishContentEntries"
                :restoring-revision-id="restoringRevisionId"
                :error-message="revisionsErrorMessage"
                @refresh="loadSelectedEntryRevisions"
                @restore="restoreSelectedEntryRevision"
              />
            </div>
          </template>
        </Card>
      </template>
    </Card>

    <BlockEditorShell
      v-if="activeBlockEditorContentType !== null"
      :content-type="activeBlockEditorContentType"
      :entry="blockEditorEntry"
      :block-fields="selectedBlockDocumentFields"
      :read-only="!canSaveBlockEditorEntry"
      :saving="blockEditorSubmitting"
      :error-message="blockEditorErrorMessage"
      @save="saveBlockEditorEntry"
      @close="requestCloseBlockEditor"
    />

    <Dialog
      :visible="dialogVisible"
      modal
      :dismissableMask="!submitting"
      :draggable="false"
      :header="dialogTitle"
      :style="{ width: 'min(72rem, 95vw)' }"
      @update:visible="handleDialogVisibilityChange"
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
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
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
  createContentEntryPreview,
  listContentEntries,
  listContentEntryRevisions,
  listContentTypes,
  publishContentEntry,
  restoreContentEntryRevision,
  unpublishContentEntry,
  updateContentEntry,
} from '@/api/content'
import { ApiClientError, asUserMessage } from '@/api/errors'
import type {
  BlockDocument,
  BlockDocumentFieldDefinition,
  ContentEntryResponse,
  ContentEntryRevisionResponse,
  ContentEntrySeoMetadata,
  ContentEntryStatus,
  ContentTypeResponse,
  RealtimeEventEnvelope,
} from '@/api/types'
import ContentEntryForm from '@/components/content/ContentEntryForm.vue'
import PublishingPanel from '@/components/content/PublishingPanel.vue'
import RevisionPanel from '@/components/content/RevisionPanel.vue'
import BlockEditorShell from '@/components/content/blocks/BlockEditorShell.vue'
import { getContentEntryDisplayTitle } from '@/features/content/form'
import { useAuthStore } from '@/stores/auth'
import { useRealtimeStore } from '@/stores/realtime'

const CONTENT_PAGE_SIZE = 50
const CONTENT_TYPE_ORDER_BY = 'updated_at'
const CONTENT_ENTRY_ORDER_BY = 'updated_at'
const REALTIME_ENTRY_REFRESH_DELAY_MS = 100

const authStore = useAuthStore()
const realtimeStore = useRealtimeStore()
const route = useRoute()
const router = useRouter()

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
const blockEditorVisible = ref(false)
const blockEditorEntry = ref<ContentEntryResponse | null>(null)
const pageErrorMessage = ref<string | null>(null)
const dialogErrorMessage = ref<string | null>(null)
const blockEditorErrorMessage = ref<string | null>(null)
const workflowEntryId = ref<string | null>(null)
const entryRevisions = ref<ContentEntryRevisionResponse[]>([])
const workflowErrorMessage = ref<string | null>(null)
const revisionsErrorMessage = ref<string | null>(null)
const previewUrl = ref<string | null>(null)
const submitting = ref(false)
const blockEditorSubmitting = ref(false)
const revisionsLoading = ref(false)
const previewLoading = ref(false)
const publishingAction = ref<'publish' | 'unpublish' | null>(null)
const restoringRevisionId = ref<string | null>(null)

const UNSAVED_CHANGES_MESSAGE = 'You have unsaved content changes. Leave without saving?'

let unsubscribeRealtime: (() => void) | null = null
let unsubscribeResync: (() => void) | null = null
let realtimeEntryRefreshTimer: ReturnType<typeof window.setTimeout> | null = null
let realtimeEntryRefreshInFlight = false
let realtimeEntryRefreshPending = false

const contentTypeOptions = computed(() =>
  contentTypes.value.map((contentType) => ({
    label: contentType.name,
    value: contentType.id,
  })),
)

const selectedContentType = computed(
  () => contentTypes.value.find((contentType) => contentType.id === selectedContentTypeId.value) ?? null,
)
const selectedBlockDocumentFields = computed<BlockDocumentFieldDefinition[]>(() => {
  return selectedContentType.value?.field_definitions.filter(
    (fieldDefinition): fieldDefinition is BlockDocumentFieldDefinition => fieldDefinition.kind === 'block_document',
  ) ?? []
})
const selectedContentTypeHasBlockDocumentFields = computed(() => selectedBlockDocumentFields.value.length > 0)
const selectedWorkflowEntry = computed(() => {
  if (entries.value.length === 0) {
    return null
  }

  return entries.value.find((entry) => entry.id === workflowEntryId.value) ?? entries.value[0]
})
const activeBlockEditorContentType = computed(() => {
  if (!blockEditorVisible.value || !selectedContentTypeHasBlockDocumentFields.value) {
    return null
  }
  return selectedContentType.value
})

const dialogTitle = computed(() => (editingEntry.value === null ? 'Create content entry' : 'Edit content entry'))
const canWriteContentEntries = computed(() => authStore.hasPermission('content.entries.write'))
const canPublishContentEntries = computed(() => authStore.hasPermission('content.entries.publish'))
const canPreviewContentEntries = computed(() => canWriteContentEntries.value || canPublishContentEntries.value)
const canReadContentTypes = computed(() => authStore.hasPermission('content.types.read'))
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
const canSaveBlockEditorEntry = computed(() => {
  if (!canWriteContentEntries.value) {
    return false
  }
  return blockEditorEntry.value === null || blockEditorEntry.value.status !== 'published' || canPublishContentEntries.value
})
const hasPotentialUnsavedChanges = computed(() => {
  const dialogHasEditableDraft = dialogVisible.value && canSaveDialogEntry.value && !submitting.value
  const blockEditorHasEditableDraft = blockEditorVisible.value && canSaveBlockEditorEntry.value && !blockEditorSubmitting.value
  return dialogHasEditableDraft || blockEditorHasEditableDraft
})

function paginationRangeLabel(offset: number, itemCount: number, total: number): string {
  if (total === 0 || itemCount === 0) {
    return '0 of 0'
  }

  return `${offset + 1}-${offset + itemCount} of ${total}`
}

function requestedContentTypeId(): string | null {
  const queryValue = route.query.contentTypeId
  if (typeof queryValue === 'string' && queryValue.trim().length > 0) {
    return queryValue
  }

  if (Array.isArray(queryValue)) {
    const firstValue = queryValue.find((value): value is string => typeof value === 'string' && value.trim().length > 0)
    return firstValue ?? null
  }

  return null
}

function selectRequestedContentType(): boolean {
  const requestedId = requestedContentTypeId()
  if (requestedId === null) {
    return false
  }

  const matchingContentType = contentTypes.value.find((contentType) => contentType.id === requestedId)
  if (!matchingContentType) {
    return false
  }

  selectedContentTypeId.value = matchingContentType.id
  return true
}

function navigateToContentModels(): void {
  void router.push('/app/content-models')
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
      workflowEntryId.value = null
      entryRevisions.value = []
      return
    }

    const hasSelectedContentType = response.items.some(
      (contentType) => contentType.id === selectedContentTypeId.value,
    )

    if (!selectRequestedContentType() && !hasSelectedContentType) {
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
    workflowEntryId.value = null
    entryRevisions.value = []
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

    if (response.items.length === 0) {
      workflowEntryId.value = null
      entryRevisions.value = []
    } else if (!response.items.some((entry) => entry.id === workflowEntryId.value)) {
      workflowEntryId.value = response.items[0].id
    }

    syncBlockEditorFromRoute()
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
    entries.value = []
    entriesTotal.value = 0
    workflowEntryId.value = null
    entryRevisions.value = []
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

function openCreateEntry(): void {
  if (selectedContentType.value === null || !canWriteContentEntries.value) {
    return
  }

  if (selectedContentTypeHasBlockDocumentFields.value) {
    openBlockEditor(null)
    return
  }

  editingEntry.value = null
  dialogErrorMessage.value = null
  dialogVisible.value = true
}

function blockEditorQueryValue(): string | null {
  const queryValue = route.query.blockEditor
  if (typeof queryValue === 'string' && queryValue.trim().length > 0) {
    return queryValue
  }

  if (Array.isArray(queryValue)) {
    const firstValue = queryValue.find((value): value is string => typeof value === 'string' && value.trim().length > 0)
    return firstValue ?? null
  }

  return null
}

function replaceBlockEditorQuery(value: string | null): void {
  const nextQuery = { ...route.query }
  if (value === null) {
    delete nextQuery.blockEditor
  } else {
    nextQuery.blockEditor = value
  }
  void router.replace({ query: nextQuery })
}

function openBlockEditor(entry: ContentEntryResponse | null): void {
  blockEditorEntry.value = entry
  blockEditorVisible.value = true
  blockEditorErrorMessage.value = null
  dialogVisible.value = false
  editingEntry.value = null
  replaceBlockEditorQuery(entry?.id ?? 'new')
}

function closeBlockEditor(): void {
  blockEditorVisible.value = false
  blockEditorEntry.value = null
  blockEditorErrorMessage.value = null
  replaceBlockEditorQuery(null)
}

function confirmDiscardUnsavedChanges(): boolean {
  return !hasPotentialUnsavedChanges.value || window.confirm(UNSAVED_CHANGES_MESSAGE)
}

function requestCloseBlockEditor(): void {
  if (!confirmDiscardUnsavedChanges()) {
    return
  }

  closeBlockEditor()
}

function handleDialogVisibilityChange(nextVisible: boolean): void {
  if (nextVisible) {
    dialogVisible.value = true
    return
  }

  if (!confirmDiscardUnsavedChanges()) {
    return
  }

  dialogVisible.value = false
}

function handleBeforeUnload(event: BeforeUnloadEvent): void {
  if (!hasPotentialUnsavedChanges.value) {
    return
  }

  event.preventDefault()
  event.returnValue = UNSAVED_CHANGES_MESSAGE
}

function syncBlockEditorFromRoute(): void {
  const queryValue = blockEditorQueryValue()
  if (queryValue === null) {
    blockEditorVisible.value = false
    blockEditorEntry.value = null
    return
  }

  if (selectedContentType.value === null || !selectedContentTypeHasBlockDocumentFields.value) {
    blockEditorVisible.value = false
    blockEditorEntry.value = null
    return
  }

  if (queryValue === 'new') {
    if (!canWriteContentEntries.value) {
      blockEditorVisible.value = false
      blockEditorEntry.value = null
      return
    }

    blockEditorEntry.value = null
    blockEditorVisible.value = true
    return
  }

  const matchingEntry = entries.value.find((entry) => entry.id === queryValue)
  if (matchingEntry === undefined) {
    blockEditorVisible.value = false
    blockEditorEntry.value = null
    return
  }

  blockEditorEntry.value = matchingEntry
  blockEditorVisible.value = true
}

function canEditEntry(entry: ContentEntryResponse): boolean {
  if (selectedContentTypeHasBlockDocumentFields.value) {
    return true
  }

  if (!canWriteContentEntries.value) {
    return false
  }

  return entry.status !== 'published' || canPublishContentEntries.value
}

function editDisabledReason(entry: ContentEntryResponse): string | undefined {
  if (selectedContentTypeHasBlockDocumentFields.value) {
    if (!canWriteContentEntries.value) {
      return 'Open read-only preview; saving requires content.entries.write.'
    }

    if (entry.status === 'published' && !canPublishContentEntries.value) {
      return 'Open read-only preview; saving published entries requires content.entries.publish.'
    }

    return undefined
  }

  if (!canWriteContentEntries.value) {
    return 'Requires content.entries.write.'
  }

  if (entry.status === 'published' && !canPublishContentEntries.value) {
    return 'Published entries require content.entries.publish.'
  }

  return undefined
}

function openEditDialog(entry: ContentEntryResponse): void {
  if (selectedContentTypeHasBlockDocumentFields.value) {
    openBlockEditor(entry)
    return
  }

  if (!canEditEntry(entry)) {
    return
  }

  editingEntry.value = entry
  dialogErrorMessage.value = null
  dialogVisible.value = true
}

function selectWorkflowEntry(entry: ContentEntryResponse): void {
  workflowEntryId.value = entry.id
  workflowErrorMessage.value = null
  revisionsErrorMessage.value = null
  previewUrl.value = null
  void loadSelectedEntryRevisions()
}

function currentWorkflowEntryOrMessage(): ContentEntryResponse | null {
  const entry = selectedWorkflowEntry.value
  if (entry === null) {
    workflowErrorMessage.value = 'Select an entry before using workflow actions.'
    return null
  }
  return entry
}

function formatEntryActionError(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.status === 409 || error.code === 'CONTENT_ENTRY_VERSION_CONFLICT') {
      return `Version conflict: ${error.detail} Refresh the entry and try again.`
    }

    if (error.status === 403 || error.code === 'PERMISSION_DENIED') {
      return `Permission denied: ${error.detail}`
    }
  }

  return asUserMessage(error)
}

async function loadSelectedEntryRevisions(): Promise<void> {
  const entry = selectedWorkflowEntry.value
  if (entry === null) {
    entryRevisions.value = []
    return
  }

  revisionsLoading.value = true
  revisionsErrorMessage.value = null

  try {
    const response = await listContentEntryRevisions(entry.id)
    entryRevisions.value = response.items
  } catch (error) {
    revisionsErrorMessage.value = formatEntryActionError(error)
    entryRevisions.value = []
  } finally {
    revisionsLoading.value = false
  }
}

function replaceEntry(updatedEntry: ContentEntryResponse): void {
  entries.value = entries.value.map((entry) => entry.id === updatedEntry.id ? updatedEntry : entry)
  workflowEntryId.value = updatedEntry.id
  if (blockEditorEntry.value?.id === updatedEntry.id) {
    blockEditorEntry.value = updatedEntry
  }
  if (editingEntry.value?.id === updatedEntry.id) {
    editingEntry.value = updatedEntry
  }
}

async function createAndOpenPreview(): Promise<void> {
  const entry = currentWorkflowEntryOrMessage()
  if (entry === null) {
    return
  }

  workflowErrorMessage.value = null
  previewLoading.value = true

  try {
    const response = await createContentEntryPreview(entry.id)
    previewUrl.value = response.preview_url
    window.open(response.preview_url, '_blank', 'noopener,noreferrer')
  } catch (error) {
    workflowErrorMessage.value = formatEntryActionError(error)
  } finally {
    previewLoading.value = false
  }
}

async function publishSelectedEntry(): Promise<void> {
  const entry = currentWorkflowEntryOrMessage()
  if (entry === null) {
    return
  }

  workflowErrorMessage.value = null
  publishingAction.value = 'publish'

  try {
    const updatedEntry = await publishContentEntry(entry.id, { expected_version: entry.version })
    replaceEntry(updatedEntry)
    await loadEntries()
    await loadSelectedEntryRevisions()
  } catch (error) {
    workflowErrorMessage.value = formatEntryActionError(error)
  } finally {
    publishingAction.value = null
  }
}

async function unpublishSelectedEntry(): Promise<void> {
  const entry = currentWorkflowEntryOrMessage()
  if (entry === null) {
    return
  }

  workflowErrorMessage.value = null
  publishingAction.value = 'unpublish'

  try {
    const updatedEntry = await unpublishContentEntry(entry.id, { expected_version: entry.version })
    replaceEntry(updatedEntry)
    await loadEntries()
    await loadSelectedEntryRevisions()
  } catch (error) {
    workflowErrorMessage.value = formatEntryActionError(error)
  } finally {
    publishingAction.value = null
  }
}

async function restoreSelectedEntryRevision(revision: ContentEntryRevisionResponse): Promise<void> {
  const entry = currentWorkflowEntryOrMessage()
  if (entry === null) {
    return
  }

  workflowErrorMessage.value = null
  revisionsErrorMessage.value = null
  restoringRevisionId.value = revision.id

  try {
    const updatedEntry = await restoreContentEntryRevision(entry.id, revision.id, { expected_version: entry.version })
    replaceEntry(updatedEntry)
    await loadEntries()
    await loadSelectedEntryRevisions()
  } catch (error) {
    revisionsErrorMessage.value = formatEntryActionError(error)
  } finally {
    restoringRevisionId.value = null
  }
}

function normalizeBlockDocument(document: BlockDocument): BlockDocument {
  const normalizeNode = (node: BlockDocument['root']): BlockDocument['root'] => ({
    type: node.type,
    props: { ...node.props },
    settings: { ...node.settings },
    children: node.children.map(normalizeNode),
  })

  return { version: 1, root: normalizeNode(document.root) }
}

function defaultPayloadValue(fieldDefinition: ContentTypeResponse['field_definitions'][number]): unknown {
  if (fieldDefinition.default_value !== undefined) {
    return fieldDefinition.default_value
  }

  switch (fieldDefinition.kind) {
    case 'text':
    case 'long_text':
    case 'rich_text':
      return fieldDefinition.required ? `Untitled ${selectedContentType.value?.name ?? 'entry'}` : ''
    case 'integer':
    case 'number':
      return 0
    case 'boolean':
      return false
    case 'date':
    case 'datetime':
      return ''
    case 'json':
      return {}
    case 'block_document':
      return null
  }
}

function buildBlockEditorPayload(document: BlockDocument): Record<string, unknown> {
  if (selectedContentType.value === null) {
    return {}
  }

  const normalizedDocument = normalizeBlockDocument(document)
  const payload: Record<string, unknown> = { ...(blockEditorEntry.value?.payload ?? {}) }

  for (const fieldDefinition of selectedContentType.value.field_definitions) {
    if (fieldDefinition.kind === 'block_document') {
      payload[fieldDefinition.name] = normalizedDocument
    } else if (payload[fieldDefinition.name] === undefined) {
      payload[fieldDefinition.name] = defaultPayloadValue(fieldDefinition)
    }
  }

  return payload
}

async function saveBlockEditorEntry(document: BlockDocument): Promise<void> {
  if (selectedContentType.value === null) {
    return
  }

  if (!canSaveBlockEditorEntry.value) {
    blockEditorErrorMessage.value = 'You do not have permission to save this block document.'
    return
  }

  blockEditorErrorMessage.value = null
  blockEditorSubmitting.value = true

  try {
    const payload = buildBlockEditorPayload(document)
    const savedEntry = blockEditorEntry.value === null
      ? await createContentEntry({
          content_type_id: selectedContentType.value.id,
          slug: null,
          status: 'draft',
          payload,
        })
      : await updateContentEntry(blockEditorEntry.value.id, {
          slug: blockEditorEntry.value.slug,
          status: blockEditorEntry.value.status,
          payload,
          seo_metadata: blockEditorEntry.value.seo_metadata,
          expected_version: blockEditorEntry.value.version,
        })

    await loadEntries()
    blockEditorEntry.value = entries.value.find((entry) => entry.id === savedEntry.id) ?? savedEntry
    blockEditorVisible.value = true
    replaceBlockEditorQuery(savedEntry.id)
  } catch (error) {
    blockEditorErrorMessage.value = formatEntryActionError(error)
  } finally {
    blockEditorSubmitting.value = false
  }
}

async function saveEntry(payload: {
  slug: string | null
  status: ContentEntryStatus
  payload: Record<string, unknown>
  seo_metadata: ContentEntrySeoMetadata
  expected_version?: number
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
        seo_metadata: payload.seo_metadata,
      })
    } else {
      await updateContentEntry(editingEntry.value.id, payload)
    }

    dialogVisible.value = false
    editingEntry.value = null
    await loadEntries()
  } catch (error) {
    dialogErrorMessage.value = formatEntryActionError(error)
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

function scheduleRealtimeEntriesRefresh(): void {
  realtimeEntryRefreshPending = true

  if (realtimeEntryRefreshTimer !== null || realtimeEntryRefreshInFlight) {
    return
  }

  realtimeEntryRefreshTimer = window.setTimeout(() => {
    realtimeEntryRefreshTimer = null
    void flushRealtimeEntriesRefresh()
  }, REALTIME_ENTRY_REFRESH_DELAY_MS)
}

async function flushRealtimeEntriesRefresh(): Promise<void> {
  if (realtimeEntryRefreshInFlight || !realtimeEntryRefreshPending) {
    return
  }

  realtimeEntryRefreshPending = false
  realtimeEntryRefreshInFlight = true

  try {
    await loadEntries()
  } finally {
    realtimeEntryRefreshInFlight = false
    if (realtimeEntryRefreshPending && realtimeEntryRefreshTimer === null) {
      realtimeEntryRefreshTimer = window.setTimeout(() => {
        realtimeEntryRefreshTimer = null
        void flushRealtimeEntriesRefresh()
      }, REALTIME_ENTRY_REFRESH_DELAY_MS)
    }
  }
}

function clearRealtimeEntriesRefresh(): void {
  if (realtimeEntryRefreshTimer !== null) {
    window.clearTimeout(realtimeEntryRefreshTimer)
    realtimeEntryRefreshTimer = null
  }
  realtimeEntryRefreshPending = false
}

function handleRealtimeEvent(event: RealtimeEventEnvelope): void {
  if (
    (event.type === 'content.entry.created'
      || event.type === 'content.entry.updated'
      || event.type === 'content.entry.deleted')
    && eventMatchesSelectedContentType(event)
  ) {
    scheduleRealtimeEntriesRefresh()
  }
}

function handleRealtimeResync(): void {
  void refreshWorkspace()
}

watch(selectedContentTypeId, async () => {
  entriesOffset.value = 0
  await loadEntries()
  syncBlockEditorFromRoute()
})

watch(() => route.query.contentTypeId, () => {
  selectRequestedContentType()
})

watch(() => route.query.blockEditor, () => {
  syncBlockEditorFromRoute()
})

watch(() => selectedWorkflowEntry.value?.id, () => {
  previewUrl.value = null
  void loadSelectedEntryRevisions()
})

onBeforeRouteLeave(() => {
  return confirmDiscardUnsavedChanges()
})

onMounted(async () => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  await loadContentTypes()
  unsubscribeRealtime = realtimeStore.subscribe(handleRealtimeEvent)
  unsubscribeResync = realtimeStore.subscribeResync(handleRealtimeResync)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  unsubscribeRealtime?.()
  unsubscribeResync?.()
  clearRealtimeEntriesRefresh()
  unsubscribeRealtime = null
  unsubscribeResync = null
})
</script>

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
          :disabled="selectedContentType === null"
          @click="openCreateDialog"
        />
      </div>
    </div>

    <Message v-if="pageErrorMessage" severity="error" :closable="false">
      {{ pageErrorMessage }}
    </Message>

    <Card>
      <template #title>Content type</template>
      <template #content>
        <div v-if="contentTypes.length === 0" class="form-stack">
          <Message severity="warn" :closable="false">
            No content types are configured yet. Create a content type through the content API first, then return here to author entries.
          </Message>
        </div>
        <div v-else class="form-grid">
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
        @submit="saveEntry"
      />
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
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
import type { ContentEntryResponse, ContentEntryStatus, ContentTypeResponse } from '@/api/types'
import ContentEntryForm from '@/components/content/ContentEntryForm.vue'
import { getContentEntryDisplayTitle } from '@/features/content/form'

const contentTypes = ref<ContentTypeResponse[]>([])
const entries = ref<ContentEntryResponse[]>([])
const selectedContentTypeId = ref<string | null>(null)
const contentTypesLoading = ref(false)
const entriesLoading = ref(false)
const dialogVisible = ref(false)
const editingEntry = ref<ContentEntryResponse | null>(null)
const pageErrorMessage = ref<string | null>(null)
const dialogErrorMessage = ref<string | null>(null)
const submitting = ref(false)

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

async function loadContentTypes(): Promise<void> {
  contentTypesLoading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listContentTypes()
    contentTypes.value = response.items
    if (response.items.length === 0) {
      selectedContentTypeId.value = null
      entries.value = []
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
    return
  }

  entriesLoading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listContentEntries({
      content_type_id: selectedContentTypeId.value,
    })
    entries.value = response.items
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
    entries.value = []
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

function openCreateDialog(): void {
  editingEntry.value = null
  dialogErrorMessage.value = null
  dialogVisible.value = true
}

function openEditDialog(entry: ContentEntryResponse): void {
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

watch(selectedContentTypeId, async () => {
  await loadEntries()
})

onMounted(async () => {
  await loadContentTypes()
})
</script>

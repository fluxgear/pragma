<template>
  <div class="page content-models">
    <div class="page__header content-models__header">
      <div>
        <h1>Content models</h1>
        <p class="muted">
          Create field schemas that power generated content entry forms and keep existing entries safe.
        </p>
      </div>
      <div class="inline-actions">
        <Button
          label="Refresh"
          icon="pi pi-refresh"
          severity="secondary"
          variant="outlined"
          :loading="loading"
          @click="loadContentModels"
        />
        <Button
          label="New model"
          icon="pi pi-plus"
          :disabled="!canManageContentTypes"
          :title="manageDisabledReason"
          data-testid="create-model"
          @click="openCreateDialog"
        />
      </div>
    </div>

    <Message v-if="pageErrorMessage" severity="error" :closable="false">
      {{ pageErrorMessage }}
    </Message>
    <Message v-if="!canManageContentTypes" severity="info" :closable="false">
      You have read-only access to content models. Create, edit, and delete actions require content.types.manage.
    </Message>

    <div v-if="createdModelForEntryHandoff !== null" class="empty-state content-models__empty">
      <h2>{{ createdModelForEntryHandoff.name }} model created</h2>
      <p class="muted">Create entries for this model now, or continue managing content models.</p>
      <Button
        type="button"
        label="Create entries"
        icon="pi pi-pencil"
        data-testid="create-entries-for-created-model"
        @click="navigateToEntriesForCreatedModel"
      />
    </div>

    <div v-if="loading" class="loading-state" role="status">Loading content models…</div>

    <div v-else-if="contentModels.length === 0" class="empty-state content-models__empty">
      <h2>No content models yet</h2>
      <p class="muted">Create a model with fields before editors author content entries.</p>
      <Button
        label="Create content model"
        icon="pi pi-plus"
        :disabled="!canManageContentTypes"
        :title="manageDisabledReason"
        @click="openCreateDialog"
      />
    </div>

    <div v-else class="content-models__grid" aria-label="Content models">
      <Card v-for="model in contentModels" :key="model.id" class="content-models__card">
        <template #title>
          <div class="content-models__card-title">
            <span>{{ model.name }}</span>
            <Tag :severity="model.can_delete ? 'success' : 'warn'" :value="deleteAvailabilityLabel(model)" />
          </div>
        </template>
        <template #content>
          <div class="content-models__card-body">
            <p v-if="model.description" class="muted">{{ model.description }}</p>
            <p v-else class="muted">No description provided.</p>

            <dl class="content-models__meta">
              <div>
                <dt>Slug</dt>
                <dd class="code-chip">{{ model.slug }}</dd>
              </div>
              <div>
                <dt>Fields</dt>
                <dd>{{ model.field_definitions.length }}</dd>
              </div>
              <div>
                <dt>Entries</dt>
                <dd>{{ model.entry_count }}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{{ formatTimestamp(model.updated_at) }}</dd>
              </div>
            </dl>

            <div class="content-models__field-chips" aria-label="Fields">
              <Tag
                v-for="field in model.field_definitions"
                :key="field.name"
                severity="secondary"
                :value="`${field.label} · ${field.kind}`"
              />
            </div>

            <div class="inline-actions content-models__actions">
              <Button
                label="Edit"
                icon="pi pi-pencil"
                severity="secondary"
                variant="outlined"
                :disabled="!canManageContentTypes"
                :title="manageDisabledReason"
                :data-testid="`edit-model-${model.id}`"
                @click="openEditDialog(model)"
              />
            </div>
          </div>
        </template>
      </Card>
    </div>

    <Dialog
      v-model:visible="dialogVisible"
      modal
      appendTo="self"
      :dismissableMask="!submitting"
      :draggable="false"
      :header="dialogTitle"
      :style="{ width: 'min(78rem, 96vw)' }"
      @hide="handleDialogHide"
    >
      <ContentModelForm
        v-if="dialogMode !== null"
        :mode="dialogMode"
        :model="editingModel"
        :error-message="dialogErrorMessage"
        :submitting="submitting"
        :can-manage="canManageContentTypes"
        @submit="saveContentModel"
        @cancel="closeDialog"
        @delete="deleteCurrentModel"
      />
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import {
  createContentType,
  deleteContentType,
  listContentTypes,
  updateContentType,
} from '@/api/content'
import { ApiClientError, asUserMessage } from '@/api/errors'
import type {
  ContentTypeCreateRequest,
  ContentTypeResponse,
  ContentTypeUpdateRequest,
} from '@/api/types'
import ContentModelForm from '@/components/content/ContentModelForm.vue'
import { useAuthStore } from '@/stores/auth'

type DialogMode = 'create' | 'edit'

const authStore = useAuthStore()
const router = useRouter()

const contentModels = ref<ContentTypeResponse[]>([])
const loading = ref(false)
const submitting = ref(false)
const pageErrorMessage = ref<string | null>(null)
const dialogErrorMessage = ref<string | null>(null)
const dialogVisible = ref(false)
const dialogMode = ref<DialogMode | null>(null)
const editingModel = ref<ContentTypeResponse | null>(null)
const createdModelForEntryHandoff = ref<ContentTypeResponse | null>(null)

const canManageContentTypes = computed(() => authStore.hasPermission('content.types.manage'))
const manageDisabledReason = computed(() =>
  canManageContentTypes.value ? undefined : 'Requires content.types.manage permission',
)
const dialogTitle = computed(() => (dialogMode.value === 'edit' ? 'Edit content model' : 'Create content model'))

onMounted(() => {
  void loadContentModels()
})

async function loadContentModels(): Promise<void> {
  loading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listContentTypes({ limit: 100, offset: 0, order_by: 'updated_at' })
    contentModels.value = response.items
  } catch (error) {
    pageErrorMessage.value = formatApiError(error)
  } finally {
    loading.value = false
  }
}

function openCreateDialog(): void {
  if (!canManageContentTypes.value) {
    return
  }

  dialogMode.value = 'create'
  editingModel.value = null
  dialogErrorMessage.value = null
  dialogVisible.value = true
}

function openEditDialog(model: ContentTypeResponse): void {
  if (!canManageContentTypes.value) {
    return
  }

  dialogMode.value = 'edit'
  editingModel.value = model
  dialogErrorMessage.value = null
  dialogVisible.value = true
}

function closeDialog(): void {
  dialogVisible.value = false
  resetDialog()
}

function handleDialogHide(): void {
  if (!dialogVisible.value) {
    resetDialog()
  }
}

function resetDialog(): void {
  if (submitting.value) {
    return
  }

  dialogMode.value = null
  editingModel.value = null
  dialogErrorMessage.value = null
}

async function saveContentModel(payload: ContentTypeCreateRequest | ContentTypeUpdateRequest): Promise<void> {
  if (!canManageContentTypes.value || dialogMode.value === null) {
    return
  }

  submitting.value = true
  dialogErrorMessage.value = null

  try {
    if (dialogMode.value === 'edit' && editingModel.value !== null) {
      await updateContentType(editingModel.value.id, payload as ContentTypeUpdateRequest)
    } else {
      createdModelForEntryHandoff.value = await createContentType(payload as ContentTypeCreateRequest)
    }

    await loadContentModels()
    closeDialog()
  } catch (error) {
    dialogErrorMessage.value = formatApiError(error)
  } finally {
    submitting.value = false
  }
}

async function deleteCurrentModel(): Promise<void> {
  if (!canManageContentTypes.value || editingModel.value === null || !editingModel.value.can_delete) {
    return
  }

  const confirmed = window.confirm(`Delete the ${editingModel.value.name} content model? This cannot be undone.`)
  if (!confirmed) {
    return
  }

  submitting.value = true
  dialogErrorMessage.value = null

  try {
    await deleteContentType(editingModel.value.id)
    await loadContentModels()
    closeDialog()
  } catch (error) {
    dialogErrorMessage.value = formatApiError(error)
  } finally {
    submitting.value = false
  }
}

function navigateToEntriesForCreatedModel(): void {
  if (createdModelForEntryHandoff.value === null) {
    return
  }

  void router.push({
    path: '/app/content',
    query: { contentTypeId: createdModelForEntryHandoff.value.id },
  })
}

function deleteAvailabilityLabel(model: ContentTypeResponse): string {
  if (model.can_delete && model.entry_count === 0) {
    return 'Delete available'
  }

  return `${model.entry_count} entr${model.entry_count === 1 ? 'y' : 'ies'} in use`
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatApiError(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === 'CONTENT_TYPE_UPDATE_INVALID') {
      return `Unsafe schema update blocked: ${error.detail}`
    }

    if (error.code === 'CONTENT_TYPE_IN_USE') {
      return `Content model is in use: ${error.detail}`
    }

    if (error.code) {
      return `${error.code}: ${error.detail}`
    }
  }

  return asUserMessage(error)
}
</script>

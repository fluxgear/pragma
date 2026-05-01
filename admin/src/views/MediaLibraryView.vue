<template>
  <div class="page media-library">
    <div class="page__header media-library__header">
      <div>
        <h1>Media library</h1>
        <p class="muted">
          Upload and browse authenticated image assets stored through Pragma's pluggable media backend.
        </p>
      </div>
      <div class="inline-actions">
        <Button
          label="Choose file"
          icon="pi pi-upload"
          severity="secondary"
          variant="outlined"
          data-testid="media-choose-file"
          :disabled="uploading || !canUploadMediaAssets"
          :title="uploadDisabledReason"
          @click="openFileDialog"
        />
        <Button
          label="Upload now"
          icon="pi pi-cloud-upload"
          data-testid="media-upload-now"
          :disabled="selectedFile === null || !canUploadMediaAssets"
          :title="uploadDisabledReason"
          :loading="uploading"
          @click="handleUpload"
        />
        <Button
          label="Refresh"
          icon="pi pi-refresh"
          severity="secondary"
          variant="outlined"
          :loading="loading"
          @click="loadAssets"
        />
      </div>
    </div>

    <input
      ref="fileInput"
      type="file"
      accept="image/png,image/jpeg,image/gif,image/webp"
      class="media-library__file-input"
      :disabled="uploading || !canUploadMediaAssets"
      @change="handleFileSelection"
    >

    <Message v-if="pageErrorMessage" severity="error" :closable="false">
      {{ pageErrorMessage }}
    </Message>
    <Message v-if="!canUploadMediaAssets" severity="info" :closable="false">
      Uploading media requires the media.assets.upload permission.
    </Message>
    <Message v-if="!canDeleteMediaAssets" severity="info" :closable="false">
      Deleting media requires the media.assets.delete permission.
    </Message>

    <Card>
      <template #title>Upload</template>
      <template #content>
        <div class="form-grid">
          <div class="field">
            <label for="media-file-name">Selected file</label>
            <InputText
              id="media-file-name"
              :modelValue="selectedFile?.name ?? ''"
              readonly
              :disabled="!canUploadMediaAssets"
              placeholder="Choose an image to upload"
            />
            <small class="muted">Supported types: PNG, JPEG, GIF, and WebP.</small>
          </div>

          <div class="field">
            <label for="media-alt-text">Alt text</label>
            <InputText
              id="media-alt-text"
              v-model.trim="uploadForm.altText"
              :disabled="uploading || !canUploadMediaAssets"
              placeholder="Describe the image for accessibility"
            />
          </div>

          <div class="field field--full">
            <label for="media-caption">Caption</label>
            <Textarea
              id="media-caption"
              v-model.trim="uploadForm.caption"
              :disabled="uploading || !canUploadMediaAssets"
              rows="3"
              autoResize
              placeholder="Optional display caption"
            />
          </div>

          <div class="field field--full">
            <label for="media-description">Description</label>
            <Textarea
              id="media-description"
              v-model.trim="uploadForm.description"
              :disabled="uploading || !canUploadMediaAssets"
              rows="4"
              autoResize
              placeholder="Optional internal description"
            />
          </div>
        </div>

        <Message v-if="uploadErrorMessage" severity="warn" :closable="false">
          {{ uploadErrorMessage }}
        </Message>
      </template>
    </Card>

    <Card>
      <template #title>Assets</template>
      <template #content>
        <DataTable
          :value="assets"
          dataKey="id"
          :loading="loading"
          responsiveLayout="scroll"
          class="media-library__table"
        >
          <Column header="Preview" style="width: 8rem;">
            <template #body="slotProps">
              <img
                v-if="slotProps.data.is_image && previewUrl(slotProps.data.id)"
                :src="previewUrl(slotProps.data.id) ?? undefined"
                :alt="slotProps.data.alt_text || slotProps.data.original_filename"
                class="media-library__thumb"
              >
              <Tag
                v-else
                severity="secondary"
                :value="slotProps.data.mime_type"
              />
            </template>
          </Column>

          <Column header="File">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <strong>{{ slotProps.data.original_filename }}</strong>
                <span class="muted code-chip">{{ slotProps.data.mime_type }}</span>
                <span class="muted">{{ formatSize(slotProps.data.size_bytes) }}</span>
              </div>
            </template>
          </Column>

          <Column header="Metadata">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <span>{{ formatDimensions(slotProps.data.width, slotProps.data.height) }}</span>
                <span class="muted">{{ slotProps.data.alt_text || 'No alt text' }}</span>
              </div>
            </template>
          </Column>

          <Column header="Updated">
            <template #body="slotProps">
              {{ formatTimestamp(slotProps.data.updated_at) }}
            </template>
          </Column>

          <Column header="Actions" style="width: 8rem;">
            <template #body="slotProps">
              <Button
                type="button"
                label="Delete"
                icon="pi pi-trash"
                severity="danger"
                variant="outlined"
                size="small"
                data-testid="media-delete"
                :disabled="!canDeleteMediaAssets"
                :title="deleteDisabledReason"
                :loading="deletingAssetId === slotProps.data.id"
                @click="removeAsset(slotProps.data.id)"
              />
            </template>
          </Column>

          <template #empty>
            <div v-if="!pageErrorMessage" class="media-library__empty-state muted">
              No media has been uploaded yet.
            </div>
          </template>
        </DataTable>

        <div class="inline-actions">
          <span class="muted" data-testid="media-pagination-summary">
            Assets {{ assetsRangeLabel }}
          </span>
          <Button
            type="button"
            label="Previous"
            severity="secondary"
            variant="outlined"
            size="small"
            data-testid="media-previous"
            :disabled="!hasPreviousAssetsPage || loading"
            @click="goToPreviousAssetsPage"
          />
          <Button
            type="button"
            label="Next"
            severity="secondary"
            variant="outlined"
            size="small"
            data-testid="media-next"
            :disabled="!hasNextAssetsPage || loading"
            @click="goToNextAssetsPage"
          />
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import {
  deleteMediaAsset,
  fetchMediaContentBlob,
  listMediaAssets,
  uploadMediaAsset,
} from '@/api/media'
import { asUserMessage } from '@/api/errors'
import type { MediaAssetResponse } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const MEDIA_PAGE_SIZE = 50
const MEDIA_ORDER_BY = 'updated_at'

const authStore = useAuthStore()

const assets = ref<MediaAssetResponse[]>([])
const previewUrls = ref<Record<string, string>>({})
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const loading = ref(false)
const uploading = ref(false)
const assetsTotal = ref(0)
const assetsLimit = ref(MEDIA_PAGE_SIZE)
const assetsOffset = ref(0)
const deletingAssetId = ref<string | null>(null)
const pageErrorMessage = ref<string | null>(null)
const uploadErrorMessage = ref<string | null>(null)
const uploadForm = reactive({
  altText: '',
  caption: '',
  description: '',
})

const canUploadMediaAssets = computed(() => authStore.hasPermission('media.assets.upload'))
const canDeleteMediaAssets = computed(() => authStore.hasPermission('media.assets.delete'))
const uploadDisabledReason = computed(() => (
  canUploadMediaAssets.value ? undefined : 'Requires media.assets.upload.'
))
const deleteDisabledReason = computed(() => (
  canDeleteMediaAssets.value ? undefined : 'Requires media.assets.delete.'
))
const assetsRangeLabel = computed(() => paginationRangeLabel(
  assetsOffset.value,
  assets.value.length,
  assetsTotal.value,
))
const hasPreviousAssetsPage = computed(() => assetsOffset.value > 0)
const hasNextAssetsPage = computed(() => assetsOffset.value + assetsLimit.value < assetsTotal.value)

function paginationRangeLabel(offset: number, itemCount: number, total: number): string {
  if (total === 0 || itemCount === 0) {
    return '0 of 0'
  }

  return `${offset + 1}-${offset + itemCount} of ${total}`
}

function openFileDialog(): void {
  if (!canUploadMediaAssets.value) {
    return
  }

  fileInput.value?.click()
}

function handleFileSelection(event: Event): void {
  const input = event.target as HTMLInputElement
  selectedFile.value = canUploadMediaAssets.value ? input.files?.[0] ?? null : null
}

function clearPreviewUrls(): void {
  Object.values(previewUrls.value).forEach((url) => URL.revokeObjectURL(url))
  previewUrls.value = {}
}

async function loadPreviewUrls(nextAssets: MediaAssetResponse[]): Promise<void> {
  clearPreviewUrls()

  await Promise.all(
    nextAssets
      .filter((asset) => asset.is_image)
      .map(async (asset) => {
        try {
          const blob = await fetchMediaContentBlob(asset.id)
          previewUrls.value[asset.id] = URL.createObjectURL(blob)
        } catch {
          previewUrls.value[asset.id] = ''
        }
      }),
  )
}

async function loadAssets(): Promise<void> {
  loading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listMediaAssets({
      limit: assetsLimit.value,
      offset: assetsOffset.value,
      order_by: MEDIA_ORDER_BY,
    })
    assets.value = response.items
    assetsTotal.value = response.total
    assetsLimit.value = response.limit
    assetsOffset.value = response.offset
    await loadPreviewUrls(response.items)
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
    assets.value = []
    assetsTotal.value = 0
    clearPreviewUrls()
  } finally {
    loading.value = false
  }
}

function resetUploadForm(): void {
  selectedFile.value = null
  uploadForm.altText = ''
  uploadForm.caption = ''
  uploadForm.description = ''
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

async function handleUpload(): Promise<void> {
  if (!canUploadMediaAssets.value) {
    uploadErrorMessage.value = 'Uploading media requires the media.assets.upload permission.'
    return
  }

  if (selectedFile.value === null) {
    return
  }

  uploading.value = true
  uploadErrorMessage.value = null

  try {
    await uploadMediaAsset(selectedFile.value, {
      alt_text: uploadForm.altText || null,
      caption: uploadForm.caption || null,
      description: uploadForm.description || null,
    })
    resetUploadForm()
    await loadAssets()
  } catch (error) {
    uploadErrorMessage.value = asUserMessage(error)
  } finally {
    uploading.value = false
  }
}

async function removeAsset(mediaId: string): Promise<void> {
  if (!canDeleteMediaAssets.value) {
    pageErrorMessage.value = 'Deleting media requires the media.assets.delete permission.'
    return
  }

  deletingAssetId.value = mediaId
  pageErrorMessage.value = null

  try {
    await deleteMediaAsset(mediaId)
    await loadAssets()
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  } finally {
    deletingAssetId.value = null
  }
}

async function goToPreviousAssetsPage(): Promise<void> {
  if (!hasPreviousAssetsPage.value) {
    return
  }

  assetsOffset.value = Math.max(0, assetsOffset.value - assetsLimit.value)
  await loadAssets()
}

async function goToNextAssetsPage(): Promise<void> {
  if (!hasNextAssetsPage.value) {
    return
  }

  assetsOffset.value += assetsLimit.value
  await loadAssets()
}

function previewUrl(mediaId: string): string | null {
  const url = previewUrls.value[mediaId] ?? ''
  return url.length > 0 ? url : null
}

function formatSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDimensions(width: number | null, height: number | null): string {
  if (width === null || height === null) {
    return 'Dimensions unavailable'
  }
  return `${width} × ${height}`
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

onMounted(async () => {
  await loadAssets()
})

onBeforeUnmount(() => {
  clearPreviewUrls()
})
</script>

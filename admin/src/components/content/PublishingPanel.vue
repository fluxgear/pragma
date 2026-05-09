<template>
  <section class="content-workflow-panel form-stack" aria-labelledby="content-workflow-title">
    <div class="content-workflow-panel__header">
      <div>
        <p class="muted">Publishing workflow</p>
        <h3 id="content-workflow-title">{{ entry.slug }}</h3>
        <p class="muted">
          Manual draft-save and publishing workflow. Automatic scheduling/autosave is not available in this backend slice.
        </p>
      </div>
      <Tag :value="entry.status" :severity="statusSeverity" />
    </div>

    <Message v-if="errorMessage" severity="error" :closable="false" data-testid="workflow-error">
      {{ errorMessage }}
    </Message>

    <dl class="content-workflow-panel__metadata" data-testid="workflow-metadata">
      <div>
        <dt>Version</dt>
        <dd>v{{ entry.version }}</dd>
      </div>
      <div>
        <dt>Revision</dt>
        <dd>{{ entry.revision_number ?? 'No revision yet' }}</dd>
      </div>
      <div>
        <dt>Updated</dt>
        <dd>{{ formatTimestamp(entry.updated_at) }}</dd>
      </div>
      <div>
        <dt>Published</dt>
        <dd>{{ entry.published_at ? formatTimestamp(entry.published_at) : 'Not published' }}</dd>
      </div>
    </dl>

    <div class="inline-actions content-workflow-panel__actions">
      <Button
        type="button"
        label="Create preview URL"
        icon="pi pi-external-link"
        severity="secondary"
        variant="outlined"
        data-testid="workflow-preview"
        :disabled="!canPreview || previewLoading"
        :loading="previewLoading"
        :title="previewDisabledReason"
        @click="emit('preview')"
      />
      <Button
        v-if="entry.status === 'draft'"
        type="button"
        label="Publish now"
        icon="pi pi-upload"
        data-testid="workflow-publish"
        :disabled="!canPublish || actionLoading"
        :loading="publishingAction === 'publish'"
        :title="publishDisabledReason"
        @click="emit('publish')"
      />
      <Button
        v-else-if="entry.status === 'published'"
        type="button"
        label="Unpublish to draft"
        icon="pi pi-download"
        severity="warn"
        data-testid="workflow-unpublish"
        :disabled="!canPublish || actionLoading"
        :loading="publishingAction === 'unpublish'"
        :title="publishDisabledReason"
        @click="emit('unpublish')"
      />
      <Tag v-else value="Archived entries cannot be manually published here" severity="warn" />
      <a
        v-if="previewUrl"
        class="content-workflow-panel__preview-link"
        :href="previewUrl"
        target="_blank"
        rel="noopener noreferrer"
        data-testid="workflow-preview-link"
      >
        Open latest preview URL
      </a>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import type { ContentEntryResponse } from '@/api/types'

const props = withDefaults(defineProps<{
  entry: ContentEntryResponse
  canPublish?: boolean
  canPreview?: boolean
  publishingAction?: 'publish' | 'unpublish' | null
  previewLoading?: boolean
  previewUrl?: string | null
  errorMessage?: string | null
}>(), {
  canPublish: false,
  canPreview: false,
  publishingAction: null,
  previewLoading: false,
  previewUrl: null,
  errorMessage: null,
})

const emit = defineEmits<{
  preview: []
  publish: []
  unpublish: []
}>()

const statusSeverity = computed(() => {
  if (props.entry.status === 'published') {
    return 'success'
  }
  if (props.entry.status === 'archived') {
    return 'warn'
  }
  return 'contrast'
})
const actionLoading = computed(() => props.publishingAction !== null)
const publishDisabledReason = computed(() => props.canPublish ? undefined : 'Requires content.entries.publish permission.')
const previewDisabledReason = computed(() => props.canPreview ? undefined : 'Requires content entry edit or publish access.')

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
</script>

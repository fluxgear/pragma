<template>
  <section class="content-revision-panel form-stack" aria-labelledby="content-revision-title">
    <div class="content-revision-panel__header">
      <div>
        <p class="muted">Revision history</p>
        <h3 id="content-revision-title">Saved revisions</h3>
        <p class="muted">Restoring writes a new current version and keeps historical revisions immutable.</p>
      </div>
      <Button
        type="button"
        label="Refresh revisions"
        icon="pi pi-refresh"
        severity="secondary"
        variant="outlined"
        size="small"
        data-testid="revisions-refresh"
        :loading="loading"
        @click="emit('refresh')"
      />
    </div>

    <Message v-if="errorMessage" severity="error" :closable="false" data-testid="revisions-error">
      {{ errorMessage }}
    </Message>
    <Message v-if="!canRestore" severity="info" :closable="false" data-testid="revisions-read-only">
      Restore requires content.entries.publish permission because it changes the current entry version.
    </Message>

    <div v-if="revisions.length === 0 && !loading" class="content-workspace__empty-state muted" data-testid="revisions-empty">
      No revision records have been created for this entry yet.
    </div>

    <ol v-else class="content-revision-panel__list" data-testid="revisions-list">
      <li v-for="revision in revisions" :key="revision.id" class="content-revision-panel__item">
        <div class="content-revision-panel__item-header">
          <div>
            <strong>Revision {{ revision.revision_number }}</strong>
            <p class="muted">{{ revision.slug }} · {{ formatTimestamp(revision.created_at) }}</p>
          </div>
          <div class="inline-actions">
            <Tag :value="revision.action" :severity="actionSeverity(revision.action)" />
            <Tag :value="revision.status" :severity="statusSeverity(revision.status)" />
          </div>
        </div>
        <p v-if="revision.restore_source_revision_id" class="muted">
          Restored from revision {{ revision.restore_source_revision_id }}.
        </p>

        <div v-if="confirmingRevisionId === revision.id" class="content-revision-panel__confirm" data-testid="revision-restore-confirm">
          <Message severity="warn" :closable="false">
            Restore revision {{ revision.revision_number }} to the current entry? This creates a new version using expected_version {{ entry.version }}.
          </Message>
          <div class="inline-actions">
            <Button
              type="button"
              label="Confirm restore"
              icon="pi pi-history"
              severity="warn"
              data-testid="revision-restore-confirm-button"
              :loading="restoringRevisionId === revision.id"
              :disabled="!canRestore || restoringRevisionId !== null"
              @click="emit('restore', revision)"
            />
            <Button type="button" label="Cancel" severity="secondary" variant="outlined" @click="confirmingRevisionId = null" />
          </div>
        </div>
        <Button
          v-else
          type="button"
          label="Restore revision"
          severity="secondary"
          variant="outlined"
          size="small"
          data-testid="revision-restore"
          :disabled="!canRestore || restoringRevisionId !== null"
          @click="confirmingRevisionId = revision.id"
        />
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import type { ContentEntryResponse, ContentEntryRevisionAction, ContentEntryRevisionResponse, ContentEntryStatus } from '@/api/types'

const props = withDefaults(defineProps<{
  entry: ContentEntryResponse
  revisions: ContentEntryRevisionResponse[]
  loading?: boolean
  canRestore?: boolean
  restoringRevisionId?: string | null
  errorMessage?: string | null
}>(), {
  loading: false,
  canRestore: false,
  restoringRevisionId: null,
  errorMessage: null,
})

const emit = defineEmits<{
  refresh: []
  restore: [revision: ContentEntryRevisionResponse]
}>()

const confirmingRevisionId = ref<string | null>(null)

watch(() => props.entry.id, () => {
  confirmingRevisionId.value = null
})

function statusSeverity(status: ContentEntryStatus): 'contrast' | 'success' | 'warn' {
  if (status === 'published') {
    return 'success'
  }
  if (status === 'archived') {
    return 'warn'
  }
  return 'contrast'
}

function actionSeverity(action: ContentEntryRevisionAction): 'contrast' | 'info' | 'success' | 'warn' {
  if (action === 'publish') {
    return 'success'
  }
  if (action === 'unpublish' || action === 'restore') {
    return 'warn'
  }
  if (action === 'update') {
    return 'info'
  }
  return 'contrast'
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
</script>

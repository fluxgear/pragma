<template>
  <div class="page">
    <div class="page__header">
      <div>
        <h1>Modules</h1>
        <p class="muted">Review discovered modules and control whether each module is enabled.</p>
      </div>
      <div class="inline-actions">
        <Button
          label="Refresh"
          icon="pi pi-refresh"
          severity="secondary"
          variant="outlined"
          :loading="loading"
          @click="loadModules"
        />
      </div>
    </div>

    <Message v-if="pageErrorMessage" severity="error" :closable="false">
      {{ pageErrorMessage }}
    </Message>
    <Message v-if="statusMessage" severity="success" closable @close="statusMessage = null">
      {{ statusMessage }}
    </Message>

    <Card>
      <template #title>Discovered modules</template>
      <template #content>
        <DataTable :value="modules" dataKey="module_id" :loading="loading" responsiveLayout="scroll">
          <Column header="Module">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <strong>{{ slotProps.data.name }}</strong>
                <span class="muted">{{ slotProps.data.module_id }} · v{{ slotProps.data.version }}</span>
              </div>
            </template>
          </Column>

          <Column header="State">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <Tag
                  :severity="slotProps.data.enabled ? 'success' : 'secondary'"
                  :value="slotProps.data.enabled ? 'Enabled' : 'Disabled'"
                />
                <Tag
                  :severity="slotProps.data.loaded ? 'success' : 'warn'"
                  :value="slotProps.data.loaded ? 'Loaded' : 'Not loaded'"
                />
              </div>
            </template>
          </Column>

          <Column header="Hooks">
            <template #body="slotProps">
              <div class="content-workspace__field-summary">
                <Tag
                  v-for="hook in slotProps.data.hooks"
                  :key="`${slotProps.data.module_id}-${hook}`"
                  severity="secondary"
                  :value="hook"
                />
                <span v-if="slotProps.data.hooks.length === 0" class="muted">No hooks registered</span>
              </div>
            </template>
          </Column>

          <Column header="Health">
            <template #body="slotProps">
              <Tag
                :severity="slotProps.data.error_code ? 'danger' : 'success'"
                :value="slotProps.data.error_code ?? 'No errors'"
              />
            </template>
          </Column>

          <Column header="Actions" style="width: 12rem;">
            <template #body="slotProps">
              <Button
                :label="slotProps.data.enabled ? 'Disable' : 'Enable'"
                size="small"
                severity="secondary"
                variant="outlined"
                data-testid="module-toggle-state"
                :loading="updatingModuleId === slotProps.data.module_id"
                @click="toggleModule(slotProps.data)"
              />
            </template>
          </Column>

          <template #empty>
            <div class="muted">No modules have been discovered by the backend runtime.</div>
          </template>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

import { asUserMessage } from '@/api/errors'
import { listModules, updateModuleState } from '@/api/modules'
import type { ModuleStateResponse } from '@/api/types'

const modules = ref<ModuleStateResponse[]>([])
const loading = ref(false)
const updatingModuleId = ref<string | null>(null)
const pageErrorMessage = ref<string | null>(null)
const statusMessage = ref<string | null>(null)

async function loadModules(): Promise<void> {
  loading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listModules()
    modules.value = response.items
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  } finally {
    loading.value = false
  }
}

async function toggleModule(moduleState: ModuleStateResponse): Promise<void> {
  updatingModuleId.value = moduleState.module_id
  pageErrorMessage.value = null
  statusMessage.value = null

  try {
    const nextEnabled = !moduleState.enabled
    await updateModuleState(moduleState.module_id, { enabled: nextEnabled })
    statusMessage.value = `${moduleState.name} ${nextEnabled ? 'enabled' : 'disabled'}.`
    await loadModules()
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  } finally {
    updatingModuleId.value = null
  }
}

onMounted(async () => {
  await loadModules()
})
</script>

<template>
  <div class="page">
    <div class="page__header">
      <h1>Dashboard</h1>
      <p class="muted">Authenticated workbench shell for future admin milestones.</p>
    </div>

    <div class="page__grid">
      <Card>
        <template #title>Session</template>
        <template #content>
          <div class="status-list">
            <div class="status-row">
              <span>User</span>
              <span>{{ user?.email }}</span>
            </div>
            <div class="status-row">
              <span>Role</span>
              <Tag :severity="user?.is_superuser ? 'info' : 'secondary'" :value="user?.is_superuser ? 'Super-admin' : 'User'" />
            </div>
            <div class="status-row">
              <span>Access token loaded</span>
              <Tag :severity="accessToken ? 'success' : 'warn'" :value="accessToken ? 'Yes' : 'No'" />
            </div>
          </div>
          <div class="inline-actions" style="margin-top: 1rem;">
            <Button label="Refresh identity" icon="pi pi-user" severity="secondary" variant="outlined" @click="refreshIdentity" />
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Platform readiness</template>
        <template #content>
          <div class="status-list">
            <div class="status-row">
              <span>Schema</span>
              <Tag :severity="schemaReady ? 'success' : 'warn'" :value="schemaReady ? 'Ready' : 'Pending'" />
            </div>
            <div class="status-row">
              <span>Readiness</span>
              <Tag :severity="readinessOk ? 'success' : 'warn'" :value="readinessOk ? 'Healthy' : 'Action required'" />
            </div>
            <div v-for="[capabilityName, capability] in capabilityEntries" :key="capabilityName" class="status-row">
              <span class="code-chip">{{ capabilityName }}</span>
              <Tag
                :severity="capability.available && capability.installed ? 'success' : 'warn'"
                :value="capability.available && capability.installed ? 'Available' : 'Unavailable'"
              />
            </div>
          </div>
          <div class="inline-actions" style="margin-top: 1rem;">
            <Button label="Refresh readiness" icon="pi pi-refresh" severity="secondary" variant="outlined" @click="refreshReadiness" />
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Admin workbench</template>
        <template #content>
          <div class="form-stack">
            <p class="muted">
              M5 brings the media library online. Content authoring and media management are now available from the authenticated workbench.
            </p>
            <div class="status-list">
              <div class="status-row">
                <span>Configured API base</span>
                <Tag severity="contrast" :value="apiBase" />
              </div>
              <div class="status-row">
                <span>Next milestone target</span>
                <Tag severity="info" value="M6 theme engine" />
              </div>
            </div>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import { useRoute, useRouter } from 'vue-router'

import { getApiBase } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useInstallStore } from '@/stores/install'

const authStore = useAuthStore()
const installStore = useInstallStore()
const route = useRoute()
const router = useRouter()

const { accessToken, user } = storeToRefs(authStore)
const { readiness, readinessOk, schemaReady } = storeToRefs(installStore)

const apiBase = getApiBase()
const capabilityEntries = computed(() => Object.entries(readiness.value?.capabilities ?? {}))

async function redirectToLogin(): Promise<void> {
  await router.replace({
    name: 'login',
    query: {
      redirect: route.fullPath,
    },
  })
}

async function refreshIdentity(): Promise<void> {
  const currentUser = await authStore.syncCurrentUser()
  if (currentUser === null) {
    await redirectToLogin()
  }
}

async function refreshReadiness(): Promise<void> {
  await installStore.loadReadiness(true)
}

onMounted(async () => {
  const [currentUser] = await Promise.all([authStore.syncCurrentUser(), installStore.loadReadiness()])
  if (currentUser === null) {
    await redirectToLogin()
  }
})
</script>

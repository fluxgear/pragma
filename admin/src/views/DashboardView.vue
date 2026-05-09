<template>
  <div class="page">
    <div class="page__header">
      <h1>Dashboard</h1>
      <p class="muted">Authenticated workbench for roles, modules, permissions, and operational status.</p>
    </div>

    <Message v-if="requiresPasswordChange" severity="warn" :closable="false">
      Your account must change its password before normal administrative work continues.
    </Message>

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
              <span>Roles</span>
              <span>{{ user?.roles.join(', ') || (user?.is_superuser ? 'super-admin' : 'none') }}</span>
            </div>
            <div class="status-row">
              <span>Access source</span>
              <Tag :severity="hasFullAccess ? 'info' : 'secondary'" :value="accessSourceLabel" />
            </div>
            <div class="status-row">
              <span>Assigned permissions</span>
              <span>{{ assignedAccessLabel }}</span>
            </div>
            <div class="status-row">
              <span>Effective access</span>
              <span>{{ effectiveAccessLabel }}</span>
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
          <Message v-if="readinessError" severity="error" :closable="false">
            {{ readinessError }}
          </Message>
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
        <template #title>Administration access</template>
        <template #content>
          <div class="status-list">
            <div class="status-row">
              <span>User administration</span>
              <Tag :severity="authStore.hasPermission('users.manage') ? 'success' : 'secondary'" :value="authStore.hasPermission('users.manage') ? 'Available' : 'Not assigned'" />
            </div>
            <div class="status-row">
              <span>Roles management</span>
              <Tag :severity="authStore.hasPermission('roles.manage') ? 'success' : 'secondary'" :value="authStore.hasPermission('roles.manage') ? 'Available' : 'Not assigned'" />
            </div>
            <div class="status-row">
              <span>AI administration</span>
              <Tag :severity="authStore.hasPermission('ai.settings.manage') ? 'success' : 'secondary'" :value="authStore.hasPermission('ai.settings.manage') ? 'Available' : 'Not assigned'" />
            </div>
            <div class="status-row">
              <span>Module administration</span>
              <Tag :severity="authStore.hasPermission('modules.manage') ? 'success' : 'secondary'" :value="authStore.hasPermission('modules.manage') ? 'Available' : 'Not assigned'" />
            </div>
            <div class="status-row">
              <span>Realtime updates</span>
              <Tag severity="info" value="Live when connected" />
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
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useInstallStore } from '@/stores/install'

const authStore = useAuthStore()
const installStore = useInstallStore()
const route = useRoute()
const router = useRouter()

const { accessToken, user, requiresPasswordChange } = storeToRefs(authStore)
const { readiness, readinessOk, schemaReady, errorMessage: readinessError } = storeToRefs(installStore)

const capabilityEntries = computed(() => Object.entries(readiness.value?.capabilities ?? {}))
const hasFullAccess = computed(() => (
  user.value?.has_all_permissions === true
  || user.value?.permission_source === 'superuser'
  || user.value?.is_superuser === true
))
const assignedPermissionCount = computed(() => user.value?.assigned_permissions.length ?? 0)
const effectivePermissionCount = computed(() => user.value?.effective_permissions.length ?? user.value?.permissions.length ?? 0)
const accessSourceLabel = computed(() => (hasFullAccess.value ? 'Superuser full access' : 'Assigned roles'))
const assignedAccessLabel = computed(() => {
  const count = assignedPermissionCount.value
  if (hasFullAccess.value && count === 0) {
    return 'No role-assigned permissions; full access via superuser'
  }
  return `${count} role-assigned permission${count === 1 ? '' : 's'}`
})
const effectiveAccessLabel = computed(() => {
  if (hasFullAccess.value) {
    return 'All permissions via superuser'
  }
  const count = effectivePermissionCount.value
  return `${count} effective permission${count === 1 ? '' : 's'}`
})

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

async function loadReadinessForDashboard(force = false): Promise<void> {
  try {
    await installStore.loadReadiness(force)
  } catch (error: unknown) {
    void error
  }
}

async function refreshReadiness(): Promise<void> {
  await loadReadinessForDashboard(true)
}

onMounted(async () => {
  const [currentUser] = await Promise.all([authStore.syncCurrentUser(), loadReadinessForDashboard()])
  if (currentUser === null) {
    await redirectToLogin()
  }
})
</script>

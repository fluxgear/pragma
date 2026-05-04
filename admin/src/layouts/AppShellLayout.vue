<template>
  <div class="shell">
    <Toolbar class="shell__toolbar">
      <template #start>
        <div class="shell__toolbar-start">
          <div>
            <strong>Pragma Admin</strong>
            <div class="muted">Admin workbench</div>
          </div>
          <Tag severity="success" value="Installed" />
        </div>
      </template>
      <template #end>
        <div class="shell__toolbar-end">
          <span class="muted">{{ user?.email }}</span>
          <Tag :severity="user?.is_superuser ? 'info' : 'secondary'" :value="roleBadge" />
          <Tag :severity="realtimeTagSeverity" :value="realtimeTagLabel" />
          <Tag v-if="requiresPasswordChange" severity="warn" value="Password change required" />
          <Button icon="pi pi-sign-out" label="Logout" severity="secondary" @click="handleLogout" />
        </div>
      </template>
    </Toolbar>

    <div class="shell__body">
      <aside class="shell__nav">
        <Panel header="Workbench">
          <div class="shell__nav-list">
            <Button
              v-for="item in navigationItems"
              :key="item.label"
              :label="item.label"
              :icon="item.icon"
              :severity="route.name === item.routeName ? 'contrast' : 'secondary'"
              :disabled="item.disabled"
              :variant="route.name === item.routeName ? undefined : 'outlined'"
              class="w-full"
              @click="navigate(item.routeName)"
            />
          </div>
        </Panel>
      </aside>

      <main class="shell__main">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import Button from 'primevue/button'
import Panel from 'primevue/panel'
import Tag from 'primevue/tag'
import Toolbar from 'primevue/toolbar'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useRealtimeStore } from '@/stores/realtime'

const authStore = useAuthStore()
const realtimeStore = useRealtimeStore()
const { user, requiresPasswordChange, isAuthenticated } = storeToRefs(authStore)
const { connectionState } = storeToRefs(realtimeStore)
const route = useRoute()
const router = useRouter()

const roleBadge = computed(() => {
  if (user.value?.is_superuser) {
    return 'Super-admin'
  }
  if (user.value?.roles.length) {
    return user.value.roles.join(', ')
  }
  return 'User'
})

const realtimeTagLabel = computed(() => {
  switch (connectionState.value) {
    case 'live':
      return 'Live'
    case 'connecting':
      return 'Connecting'
    case 'reconnecting':
      return 'Reconnecting'
    default:
      return 'Offline'
  }
})

const realtimeTagSeverity = computed(() => {
  switch (connectionState.value) {
    case 'live':
      return 'success'
    case 'connecting':
      return 'info'
    case 'reconnecting':
      return 'warn'
    default:
      return 'secondary'
  }
})

const navigationItems = computed(() => [
  { label: 'Dashboard', icon: 'pi pi-home', routeName: 'dashboard', disabled: false },
  {
    label: 'Content',
    icon: 'pi pi-file-edit',
    routeName: 'content',
    disabled: !authStore.hasPermission('content.entries.read'),
  },
  {
    label: 'Media',
    icon: 'pi pi-images',
    routeName: 'media',
    disabled: !authStore.hasPermission('media.assets.read'),
  },
  {
    label: 'AI settings',
    icon: 'pi pi-sparkles',
    routeName: 'ai-settings',
    disabled: !authStore.hasPermission('ai.settings.manage'),
  },
  {
    label: 'Modules',
    icon: 'pi pi-box',
    routeName: 'modules',
    disabled: !authStore.hasPermission('modules.manage'),
  },
  {
    label: 'Users',
    icon: 'pi pi-users',
    routeName: 'users',
    disabled: !authStore.hasPermission('users.manage'),
  },
  {
    label: 'Account',
    icon: 'pi pi-user',
    routeName: 'account',
    disabled: false,
  },
])

watch(
  [isAuthenticated, requiresPasswordChange],
  ([authenticated, passwordChangeRequired]) => {
    if (authenticated && !passwordChangeRequired) {
      realtimeStore.start()
      return
    }
    realtimeStore.stop()
  },
  { immediate: true },
)

onMounted(() => {
  if (isAuthenticated.value && !requiresPasswordChange.value) {
    realtimeStore.start()
  }
})

onUnmounted(() => {
  realtimeStore.stop()
})

function navigate(routeName: string): void {
  if (route.name !== routeName) {
    void router.push({ name: routeName })
  }
}

async function handleLogout(): Promise<void> {
  realtimeStore.stop()
  await authStore.logout()
  await router.push({ name: 'login' })
}
</script>

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
          <Tag :severity="user?.is_superuser ? 'info' : 'secondary'" :value="user?.is_superuser ? 'Super-admin' : 'User'" />
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
import { storeToRefs } from 'pinia'
import Button from 'primevue/button'
import Panel from 'primevue/panel'
import Tag from 'primevue/tag'
import Toolbar from 'primevue/toolbar'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)
const route = useRoute()
const router = useRouter()

const navigationItems = [
  { label: 'Dashboard', icon: 'pi pi-home', routeName: 'dashboard', disabled: false },
  { label: 'Content', icon: 'pi pi-file-edit', routeName: 'content', disabled: false },
  { label: 'Media', icon: 'pi pi-images', routeName: 'media', disabled: false },
  { label: 'Themes (M6)', icon: 'pi pi-palette', routeName: 'dashboard', disabled: true },
]

function navigate(routeName: string): void {
  if (route.name !== routeName) {
    void router.push({ name: routeName })
  }
}

async function handleLogout(): Promise<void> {
  await authStore.logout()
  await router.push({ name: 'login' })
}
</script>

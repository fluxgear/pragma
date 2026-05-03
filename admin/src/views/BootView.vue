<template>
  <div class="auth-layout">
    <div class="form-stack" style="align-items: center;">
      <Message v-if="bootstrapErrorMessage" severity="error" :closable="false">
        {{ bootstrapErrorMessage }}
      </Message>
      <template v-else>
        <ProgressSpinner strokeWidth="4" />
        <span class="muted">Loading installation and session state…</span>
      </template>
      <Button
        v-if="bootstrapErrorMessage"
        label="Retry startup checks"
        icon="pi pi-refresh"
        :loading="isRetrying || statusLoading || authLoading"
        @click="retryBootstrap"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import Button from 'primevue/button'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import { useRouter } from 'vue-router'

import { evaluateNavigation } from '@/router/guards'
import { useAuthStore } from '@/stores/auth'
import { useInstallStore } from '@/stores/install'

const authStore = useAuthStore()
const installStore = useInstallStore()
const router = useRouter()
const isRetrying = ref(false)

const { errorMessage: authErrorMessage, loading: authLoading } = storeToRefs(authStore)
const { errorMessage: installErrorMessage, statusLoading } = storeToRefs(installStore)

const bootstrapErrorMessage = computed(() => installErrorMessage.value ?? authErrorMessage.value ?? null)

async function retryBootstrap(): Promise<void> {
  isRetrying.value = true

  try {
    await installStore.loadStatus(true)
    authStore.clearSession(false)
    authStore.errorMessage = null
    await authStore.ensureInitialized(installStore.isInstalled)

    if (installStore.isInstalled && authStore.errorMessage) {
      return
    }

    const nextRoute = evaluateNavigation(
      {
        name: 'home',
        fullPath: '/',
        meta: {},
      },
      {
        isInstalled: installStore.isInstalled,
        isAuthenticated: authStore.isAuthenticated,
        isSuperuser: authStore.user?.is_superuser === true,
        permissions: authStore.user?.permissions ?? [],
        forcePasswordChange: authStore.user?.force_password_change === true,
      },
    )

    if (nextRoute !== true) {
      await router.replace(nextRoute)
    }
  } catch {
    // Store state already carries the structured error message.
  } finally {
    isRetrying.value = false
  }
}
</script>

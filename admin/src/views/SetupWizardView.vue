<template>
  <div class="page">
    <div class="page__header">
      <h2>Setup wizard · phase 1</h2>
      <p class="muted">
        Confirm backend readiness, create the first super-admin, and transition directly into the admin shell.
      </p>
    </div>

    <Message v-if="errorMessage" severity="error" :closable="false">
      {{ errorMessage }}
    </Message>

    <div class="page__grid">
      <Card>
        <template #title>System readiness</template>
        <template #content>
          <div class="status-list">
            <div class="status-row">
              <span>Schema migrated</span>
              <Tag :severity="schemaReady ? 'success' : 'warn'" :value="schemaReady ? 'Ready' : 'Pending'" />
            </div>
            <div class="status-row">
              <span>Install flag</span>
              <Tag :severity="isInstalled ? 'success' : 'contrast'" :value="isInstalled ? 'Installed' : 'Not installed'" />
            </div>
            <div class="status-row">
              <span>Readiness endpoint</span>
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
            <Button
              label="Refresh checks"
              icon="pi pi-refresh"
              severity="secondary"
              variant="outlined"
              :loading="statusLoading || readinessLoading"
              @click="refreshChecks"
            />
          </div>
        </template>
      </Card>

      <Card>
        <template #title>First super-admin</template>
        <template #content>
          <form class="form-stack" @submit.prevent="handleSubmit">
            <Message severity="info" :closable="false">
              Phase 1 uses the existing backend bootstrap contract. Site identity and broader onboarding settings stay deferred until a later milestone.
            </Message>

            <div class="form-grid">
              <div class="field">
                <label for="setup-email">Email</label>
                <InputText id="setup-email" v-model.trim="form.email" autocomplete="email" required />
              </div>

              <div class="field">
                <label for="setup-username">Username</label>
                <InputText id="setup-username" v-model.trim="form.username" autocomplete="username" required />
              </div>

              <div class="field field--full">
                <label for="setup-full-name">Full name</label>
                <InputText id="setup-full-name" v-model.trim="form.fullName" autocomplete="name" />
              </div>

              <div class="field">
                <label for="setup-password">Password</label>
                <Password
                  v-model="form.password"
                  inputId="setup-password"
                  autocomplete="new-password"
                  toggleMask
                  required
                />
              </div>

              <div class="field">
                <label for="setup-confirm-password">Confirm password</label>
                <Password
                  v-model="form.confirmPassword"
                  inputId="setup-confirm-password"
                  autocomplete="new-password"
                  :feedback="false"
                  toggleMask
                  required
                />
              </div>
            </div>

            <Message v-if="passwordMismatch" severity="warn" :closable="false">
              Password confirmation does not match.
            </Message>

            <div class="inline-actions">
              <Button
                type="submit"
                label="Complete setup"
                icon="pi pi-check"
                :loading="submitting"
                :disabled="!canSubmit"
              />
              <Button
                type="button"
                label="Go to login"
                severity="secondary"
                variant="outlined"
                @click="goToLogin"
              />
            </div>
          </form>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { storeToRefs } from 'pinia'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import Tag from 'primevue/tag'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useInstallStore } from '@/stores/install'

const authStore = useAuthStore()
const installStore = useInstallStore()
const router = useRouter()

const {
  errorMessage,
  isInstalled,
  readiness,
  readinessLoading,
  readinessOk,
  schemaReady,
  status,
  statusLoading,
  submitting,
} = storeToRefs(installStore)

const form = reactive({
  email: '',
  username: '',
  fullName: '',
  password: '',
  confirmPassword: '',
})

const passwordMismatch = computed(
  () => form.confirmPassword.length > 0 && form.password !== form.confirmPassword,
)

const capabilityEntries = computed(() => Object.entries(readiness.value?.capabilities ?? status.value?.capabilities ?? {}))

const canSubmit = computed(
  () => schemaReady.value && readinessOk.value && !passwordMismatch.value && form.password.length >= 12,
)

async function refreshChecks(): Promise<void> {
  await installStore.refreshAll()
}

async function handleSubmit(): Promise<void> {
  if (!canSubmit.value) {
    return
  }

  try {
    await installStore.bootstrapAdmin({
      email: form.email,
      username: form.username,
      password: form.password,
      full_name: form.fullName || null,
    })

    try {
      await authStore.login({
        identity: form.email,
        password: form.password,
      })
      await installStore.refreshAll()
      await router.push({ name: 'dashboard' })
    } catch {
      await router.push({ name: 'login', query: { setup: 'complete' } })
    }
  } catch {
    // Structured error state is surfaced from the store.
  }
}

async function goToLogin(): Promise<void> {
  await router.push({ name: 'login' })
}

onMounted(async () => {
  await installStore.refreshAll()
})
</script>

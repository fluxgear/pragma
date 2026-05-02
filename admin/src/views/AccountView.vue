<template>
  <div class="page">
    <div class="page__header">
      <h1>Account</h1>
      <p class="muted">Change your password and clear forced-password-rotation requirements.</p>
    </div>

    <Message v-if="requiresPasswordChange" severity="warn" :closable="false">
      Your current session is restricted until you choose a new password.
    </Message>
    <Message v-if="errorMessage" severity="error" :closable="false">
      {{ errorMessage }}
    </Message>
    <Message v-if="successMessage" severity="success" :closable="false">
      {{ successMessage }}
    </Message>

    <Card>
      <template #title>Password</template>
      <template #content>
        <form class="form-stack" @submit.prevent="submitPasswordChange">
          <div class="field">
            <label for="current-password">Current password</label>
            <Password inputId="current-password" v-model="form.currentPassword" toggleMask :feedback="false" />
          </div>
          <div class="field">
            <label for="new-password">New password</label>
            <Password inputId="new-password" v-model="form.newPassword" toggleMask :feedback="false" />
          </div>
          <div class="field">
            <label for="confirm-password">Confirm new password</label>
            <Password inputId="confirm-password" v-model="form.confirmPassword" toggleMask :feedback="false" />
          </div>

          <div class="inline-actions">
            <Button label="Change password" icon="pi pi-key" type="submit" :loading="submitting" />
          </div>
        </form>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Message from 'primevue/message'
import Password from 'primevue/password'

import { asUserMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const { requiresPasswordChange } = storeToRefs(authStore)

const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const submitting = ref(false)
const errorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)

async function submitPasswordChange(): Promise<void> {
  errorMessage.value = null
  successMessage.value = null

  if (form.newPassword !== form.confirmPassword) {
    errorMessage.value = 'The new password confirmation does not match.'
    return
  }

  submitting.value = true
  try {
    await authStore.rotateOwnPassword({
      current_password: form.currentPassword,
      new_password: form.newPassword,
    })
    form.currentPassword = ''
    form.newPassword = ''
    form.confirmPassword = ''
    successMessage.value = 'Password changed successfully. Please sign in again.'
    await router.replace({ name: 'login', query: { passwordChanged: '1' } })
  } catch (error) {
    errorMessage.value = asUserMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

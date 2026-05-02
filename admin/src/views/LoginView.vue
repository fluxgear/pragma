<template>
  <form class="form-stack" @submit.prevent="handleSubmit">
    <Message v-if="successMessage" severity="success" :closable="false">
      {{ successMessage }}
    </Message>
    <Message v-if="errorMessage" severity="error" :closable="false">
      {{ errorMessage }}
    </Message>

    <div class="field">
      <label for="login-identity">Email or username</label>
      <InputText id="login-identity" v-model.trim="identity" autocomplete="username" required />
    </div>

    <div class="field">
      <label for="login-password">Password</label>
      <Password
        v-model="password"
        inputId="login-password"
        autocomplete="current-password"
        :feedback="false"
        toggleMask
        required
      />
    </div>

    <div class="inline-actions">
      <Button type="submit" label="Sign in" icon="pi pi-sign-in" :loading="loading" />
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const { errorMessage, loading } = storeToRefs(authStore)
const route = useRoute()
const router = useRouter()

const identity = ref('')
const password = ref('')

const successMessage = computed(() => {
  if (route.query.setup === 'complete') {
    return 'Setup is complete. Sign in with the super-admin account you just created.'
  }

  if (route.query.passwordChanged === '1') {
    return 'Password changed successfully. Please sign in again.'
  }

  return null
})

function resolveRedirect(): string | null {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.length > 0) {
    return redirect
  }

  return null
}

async function handleSubmit(): Promise<void> {
  try {
    await authStore.login({
      identity: identity.value,
      password: password.value,
    })

    const redirect = resolveRedirect()
    await router.push(redirect ?? { name: 'dashboard' })
  } catch {
    // Store state already carries the structured error message.
  }
}

</script>

<template>
  <Card>
    <template #title>Route not found</template>
    <template #content>
      <div class="form-stack">
        <p class="muted">The requested admin route does not exist.</p>
        <div class="inline-actions">
          <Button label="Back to start" icon="pi pi-home" @click="goToHome" />
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import Card from 'primevue/card'
import { useRouter } from 'vue-router'

const router = useRouter()

async function goToHome(): Promise<void> {
  await router.push({ name: 'home' })
}
</script>

<template>
  <Card>
    <template #title>Route not found</template>
    <template #content>
      <div class="form-stack">
        <p class="muted">The requested admin route does not exist in the current milestone shell.</p>
        <div class="inline-actions">
          <Button label="Back to dashboard" icon="pi pi-home" @click="goToDashboard" />
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

async function goToDashboard(): Promise<void> {
  await router.push({ name: 'dashboard' })
}
</script>

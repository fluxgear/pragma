<template>
  <div class="auth-layout">
    <Card class="auth-layout__panel">
      <template #content>
        <div class="auth-layout__header">
          <Tag severity="contrast" value="Pragma M3" />
          <h1>Admin shell + setup wizard</h1>
          <p class="muted">
            Install-aware onboarding and authenticated admin routing for Pragma.
          </p>
        </div>
        <RouterView />
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import { RouterView } from 'vue-router'
</script>

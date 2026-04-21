<template>
  <div class="auth-layout">
    <div class="form-stack" style="align-items: center;">
      <ProgressSpinner strokeWidth="4" />
      <span class="muted">Loading installation and session state…</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import ProgressSpinner from 'primevue/progressspinner'
</script>

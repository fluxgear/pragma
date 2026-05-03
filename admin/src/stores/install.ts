import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { asUserMessage } from '@/api/errors'
import { bootstrapInstall, fetchInstallStatus } from '@/api/install'
import { fetchReadinessStatus } from '@/api/system'
import type { BootstrapRequest, BootstrapResponse, InstallStatusResponse, ReadinessResponse } from '@/api/types'

export const useInstallStore = defineStore('install', () => {
  const status = ref<InstallStatusResponse | null>(null)
  const readiness = ref<ReadinessResponse | null>(null)
  const statusLoading = ref(false)
  const readinessLoading = ref(false)
  const submitting = ref(false)
  const errorMessage = ref<string | null>(null)

  const isInstalled = computed(() => status.value?.is_installed ?? false)
  const schemaReady = computed(() => status.value?.schema_ready ?? false)
  const readinessOk = computed(
    () => readiness.value?.status === 'ok' && readiness.value?.database === 'up' && readiness.value?.schema_ready === true,
  )

  async function loadStatus(force = false): Promise<InstallStatusResponse> {
    if (status.value !== null && !force) {
      return status.value
    }

    statusLoading.value = true
    errorMessage.value = null

    try {
      const response = await fetchInstallStatus()
      status.value = response
      return response
    } catch (error) {
      errorMessage.value = asUserMessage(error)
      throw error
    } finally {
      statusLoading.value = false
    }
  }

  async function loadReadiness(force = false): Promise<ReadinessResponse> {
    if (readiness.value !== null && !force) {
      return readiness.value
    }

    readinessLoading.value = true
    errorMessage.value = null

    try {
      const response = await fetchReadinessStatus()
      readiness.value = response
      return response
    } catch (error) {
      errorMessage.value = asUserMessage(error)
      throw error
    } finally {
      readinessLoading.value = false
    }
  }

  async function ensureStatus(): Promise<InstallStatusResponse> {
    if (status.value !== null) {
      return status.value
    }

    return loadStatus()
  }

  async function refreshAll(): Promise<void> {
    await Promise.all([loadStatus(true), loadReadiness(true)])
  }

  async function bootstrapAdmin(
    payload: BootstrapRequest,
    setupSecret?: string | null,
  ): Promise<BootstrapResponse> {
    submitting.value = true
    errorMessage.value = null

    try {
      const latestReadiness = await loadReadiness(true)
      if (latestReadiness.status !== 'ok' || latestReadiness.database !== 'up' || !latestReadiness.schema_ready) {
        const message = 'Backend readiness checks must pass before setup can complete.'
        errorMessage.value = message
        throw new Error(message)
      }

      const response = await bootstrapInstall(payload, setupSecret)
      await loadStatus(true)
      return response
    } catch (error) {
      errorMessage.value = asUserMessage(error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  return {
    status,
    readiness,
    statusLoading,
    readinessLoading,
    submitting,
    errorMessage,
    isInstalled,
    schemaReady,
    readinessOk,
    loadStatus,
    loadReadiness,
    ensureStatus,
    refreshAll,
    bootstrapAdmin,
  }
})

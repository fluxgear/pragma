import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { changePassword, getCurrentUser, loginUser, logoutUser, refreshSession } from '@/api/auth'
import { ApiClientError, asUserMessage } from '@/api/errors'
import type {
  ChangePasswordRequest,
  LoginRequest,
  TokenResponse,
  UserResponse,
} from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null)
  const expiresIn = ref<number | null>(null)
  const user = ref<UserResponse | null>(null)
  const initialized = ref(false)
  const loading = ref(false)
  const errorMessage = ref<string | null>(null)
  const startupError = ref<string | null>(null)

  const isAuthenticated = computed(() => accessToken.value !== null && user.value !== null)
  const requiresPasswordChange = computed(() => user.value?.force_password_change === true)

  function setSession(payload: TokenResponse): void {
    accessToken.value = payload.access_token
    expiresIn.value = payload.expires_in
    user.value = payload.user
    initialized.value = true
    errorMessage.value = null
    startupError.value = null
  }

  function clearSession(markInitialized = true): void {
    accessToken.value = null
    expiresIn.value = null
    user.value = null
    initialized.value = markInitialized
    startupError.value = null
  }

  function hasPermission(permission: string): boolean {
    if (user.value === null) {
      return false
    }
    if (user.value.is_superuser) {
      return true
    }
    return user.value.permissions.includes(permission)
  }

  async function login(payload: LoginRequest): Promise<TokenResponse> {
    loading.value = true
    errorMessage.value = null
    startupError.value = null

    try {
      const response = await loginUser(payload)
      setSession(response)
      return response
    } catch (error) {
      clearSession(false)
      initialized.value = true
      errorMessage.value = asUserMessage(error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function restoreSession(): Promise<boolean> {
    loading.value = true
    errorMessage.value = null
    startupError.value = null

    try {
      const response = await refreshSession()
      setSession(response)
      return true
    } catch (error) {
      const message =
        error instanceof ApiClientError && error.status === 401 ? null : asUserMessage(error)

      clearSession()
      errorMessage.value = message
      startupError.value = message
      return false
    } finally {
      loading.value = false
      initialized.value = true
    }
  }

  async function ensureInitialized(shouldRestore: boolean): Promise<void> {
    if (initialized.value) {
      return
    }

    if (!shouldRestore) {
      initialized.value = true
      return
    }

    await restoreSession()
  }

  async function syncCurrentUser(): Promise<UserResponse | null> {
    if (!accessToken.value) {
      return null
    }

    try {
      const currentUser = await getCurrentUser(accessToken.value)
      user.value = currentUser
      return currentUser
    } catch (error) {
      clearSession()
      errorMessage.value = asUserMessage(error)
      return null
    }
  }

  async function rotateOwnPassword(payload: ChangePasswordRequest): Promise<UserResponse> {
    if (accessToken.value === null) {
      throw new Error('Authentication required')
    }

    const updatedUser = await changePassword(accessToken.value, payload)
    user.value = updatedUser
    return updatedUser
  }

  async function logout(): Promise<void> {
    loading.value = true

    try {
      if (isAuthenticated.value) {
        await logoutUser()
      }
    } finally {
      clearSession()
      loading.value = false
      errorMessage.value = null
    }
  }

  return {
    accessToken,
    expiresIn,
    user,
    initialized,
    loading,
    errorMessage,
    startupError,
    isAuthenticated,
    requiresPasswordChange,
    hasPermission,
    login,
    restoreSession,
    ensureInitialized,
    syncCurrentUser,
    rotateOwnPassword,
    logout,
    clearSession,
  }
})

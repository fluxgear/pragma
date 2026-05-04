<template>
  <div class="page">
    <div class="page__header">
      <div>
        <h1>Users</h1>
        <p class="muted">Manage user accounts, role assignments, activation state, and password resets.</p>
      </div>
      <div class="inline-actions">
        <Button label="Refresh" icon="pi pi-refresh" severity="secondary" variant="outlined" :loading="loading" @click="loadData" />
        <Button label="New user" icon="pi pi-user-plus" @click="openCreateDialog" />
      </div>
    </div>

    <Message v-if="pageErrorMessage" severity="error" :closable="false">
      {{ pageErrorMessage }}
    </Message>

    <Card>
      <template #title>Accounts</template>
      <template #content>
        <DataTable :value="users" dataKey="id" :loading="loading" responsiveLayout="scroll">
          <Column header="User">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <strong>{{ slotProps.data.full_name || slotProps.data.username }}</strong>
                <span class="muted">{{ slotProps.data.email }}</span>
              </div>
            </template>
          </Column>

          <Column header="Roles">
            <template #body="slotProps">
              <div class="content-workspace__field-summary">
                <Tag
                  v-for="role in slotProps.data.roles"
                  :key="`${slotProps.data.id}-${role}`"
                  severity="secondary"
                  :value="role"
                />
                <Tag v-if="slotProps.data.is_superuser" severity="info" value="super-admin" />
              </div>
            </template>
          </Column>

          <Column header="Status">
            <template #body="slotProps">
              <div class="form-stack" style="gap: 0.25rem;">
                <Tag :severity="slotProps.data.is_active ? 'success' : 'warn'" :value="slotProps.data.is_active ? 'Active' : 'Inactive'" />
                <Tag v-if="slotProps.data.force_password_change" severity="warn" value="Password change required" />
              </div>
            </template>
          </Column>

          <Column header="Actions" style="width: 22rem;">
            <template #body="slotProps">
              <div class="inline-actions">
                <Button label="Roles" size="small" severity="secondary" variant="outlined" @click="openRolesDialog(slotProps.data)" />
                <Button
                  :label="slotProps.data.is_active ? 'Deactivate' : 'Activate'"
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  data-testid="user-toggle-active"
                  @click="openActiveDialog(slotProps.data)"
                />
                <Button
                  label="Reset password"
                  size="small"
                  severity="warn"
                  variant="outlined"
                  data-testid="user-reset-password"
                  @click="openPasswordResetDialog(slotProps.data)"
                />
              </div>
            </template>
          </Column>

          <template #empty>
            <div class="muted">No managed users have been created yet.</div>
          </template>
        </DataTable>

        <div class="inline-actions" style="justify-content: space-between; margin-top: 1rem;">
          <span class="muted">
            Showing {{ pageStart }}-{{ pageEnd }} of {{ usersTotal }} users
          </span>
          <div class="inline-actions">
            <Button label="Previous" severity="secondary" variant="outlined" :disabled="!canGoPrevious || loading" @click="loadPreviousUsers" />
            <Button label="Next" severity="secondary" variant="outlined" :disabled="!canGoNext || loading" @click="loadNextUsers" />
          </div>
        </div>
      </template>
    </Card>

    <Dialog v-model:visible="createDialogVisible" modal :draggable="false" :style="{ width: 'min(40rem, 95vw)' }" header="Create user">
      <form class="form-stack" @submit.prevent="submitCreateUser">
        <div class="field">
          <label for="create-email">Email</label>
          <InputText id="create-email" v-model.trim="createForm.email" />
        </div>
        <div class="field">
          <label for="create-username">Username</label>
          <InputText id="create-username" v-model.trim="createForm.username" />
        </div>
        <div class="field">
          <label for="create-full-name">Full name</label>
          <InputText id="create-full-name" v-model.trim="createForm.fullName" />
        </div>
        <div class="field">
          <label for="create-password">Initial password</label>
          <Password inputId="create-password" v-model="createForm.password" toggleMask :feedback="false" />
        </div>
        <div class="field">
          <label for="create-roles">Roles</label>
          <MultiSelect id="create-roles" v-model="createForm.roleKeys" :options="roleOptions" optionLabel="label" optionValue="value" display="chip" />
        </div>
        <div class="field field__checkbox-row">
          <Checkbox id="create-force-change" v-model="createForm.forcePasswordChange" :binary="true" />
          <label for="create-force-change">Require password change on first login</label>
        </div>
        <div class="field field__checkbox-row">
          <Checkbox id="create-active" v-model="createForm.isActive" :binary="true" />
          <label for="create-active">Account active</label>
        </div>
        <Message v-if="dialogErrorMessage" severity="error" :closable="false">{{ dialogErrorMessage }}</Message>
        <div class="inline-actions">
          <Button label="Create" icon="pi pi-check" type="submit" :loading="dialogSubmitting" />
        </div>
      </form>
    </Dialog>

    <Dialog v-model:visible="rolesDialogVisible" modal :draggable="false" :style="{ width: 'min(36rem, 95vw)' }" header="Update roles">
      <form class="form-stack" @submit.prevent="submitRoleUpdate">
        <div class="field">
          <label for="role-assignment">Roles</label>
          <MultiSelect id="role-assignment" v-model="rolesForm.roleKeys" :options="roleOptions" optionLabel="label" optionValue="value" display="chip" />
        </div>
        <Message v-if="dialogErrorMessage" severity="error" :closable="false">{{ dialogErrorMessage }}</Message>
        <div class="inline-actions">
          <Button label="Save roles" icon="pi pi-save" type="submit" :loading="dialogSubmitting" />
        </div>
      </form>
    </Dialog>

    <Dialog
      v-model:visible="userActionDialogVisible"
      modal
      :draggable="false"
      :style="{ width: 'min(34rem, 95vw)' }"
      :header="userActionDialogTitle"
    >
      <div class="form-stack">
        <p>{{ userActionDialogMessage }}</p>
        <Message severity="warn" :closable="false">
          {{ userActionWarning }}
        </Message>
        <div class="inline-actions">
          <Button
            label="Cancel"
            severity="secondary"
            variant="outlined"
            @click="closeUserActionDialog"
          />
          <Button
            :label="userActionConfirmLabel"
            :severity="userActionConfirmSeverity"
            data-testid="user-confirm-action"
            :loading="dialogSubmitting"
            @click="confirmUserAction"
          />
        </div>
      </div>
    </Dialog>

    <Dialog
      v-model:visible="temporaryPasswordDialogVisible"
      modal
      :draggable="false"
      :closable="false"
      :style="{ width: 'min(34rem, 95vw)' }"
      header="Temporary password ready"
    >
      <div class="form-stack">
        <Message severity="warn" :closable="false">
          This temporary password is stored only in this dialog. It clears when closed, when the timer expires, or when you leave this page.
        </Message>
        <p class="muted">
          Copy the credential now or reveal it once for secure transfer. It will not remain in a page banner.
        </p>
        <div v-if="temporaryPasswordRevealed" class="form-stack" style="gap: 0.5rem;">
          <span class="muted">Temporary password</span>
          <code data-testid="temporary-password-value" class="code-chip">{{ temporaryPasswordSecret }}</code>
        </div>
        <Message v-if="temporaryPasswordCopyMessage" severity="info" :closable="false">
          {{ temporaryPasswordCopyMessage }}
        </Message>
        <div class="inline-actions">
          <Button
            v-if="!temporaryPasswordRevealed"
            label="Reveal one time"
            severity="secondary"
            variant="outlined"
            data-testid="temporary-password-reveal"
            @click="revealTemporaryPassword"
          />
          <Button
            label="Copy password"
            severity="secondary"
            variant="outlined"
            data-testid="temporary-password-copy"
            @click="copyTemporaryPassword"
          />
          <Button
            label="Close and clear"
            severity="warn"
            data-testid="temporary-password-close"
            @click="clearTemporaryPassword"
          />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import MultiSelect from 'primevue/multiselect'
import Password from 'primevue/password'
import Tag from 'primevue/tag'

import { asUserMessage } from '@/api/errors'
import { createUser, listRoles, listUsers, replaceUserRoles, resetUserPassword, updateUser } from '@/api/users'
import type { AdminUserResponse, RoleResponse } from '@/api/types'

const USERS_PAGE_SIZE = 50

const users = ref<AdminUserResponse[]>([])
const usersTotal = ref(0)
const usersLimit = ref(USERS_PAGE_SIZE)
const usersOffset = ref(0)
const roles = ref<RoleResponse[]>([])
const loading = ref(false)
const pageErrorMessage = ref<string | null>(null)
const temporaryPasswordDialogVisible = ref(false)
const temporaryPasswordSecret = ref<string | null>(null)
const temporaryPasswordRevealed = ref(false)
const temporaryPasswordCopyMessage = ref<string | null>(null)
let temporaryPasswordClearTimer: ReturnType<typeof setTimeout> | null = null
const dialogErrorMessage = ref<string | null>(null)
const dialogSubmitting = ref(false)
const createDialogVisible = ref(false)
const rolesDialogVisible = ref(false)
const userActionDialogVisible = ref(false)
const selectedUser = ref<AdminUserResponse | null>(null)
const selectedActionUser = ref<AdminUserResponse | null>(null)
const pendingUserAction = ref<'toggle-active' | 'reset-password' | null>(null)

const createForm = reactive({
  email: '',
  username: '',
  fullName: '',
  password: '',
  roleKeys: [] as string[],
  forcePasswordChange: true,
  isActive: true,
})

const rolesForm = reactive({
  roleKeys: [] as string[],
})

const roleOptions = computed(() =>
  roles.value.map((role) => ({
    label: role.name,
    value: role.role_key,
  })),
)
const pageStart = computed(() => (usersTotal.value === 0 ? 0 : usersOffset.value + 1))
const pageEnd = computed(() => Math.min(usersOffset.value + users.value.length, usersTotal.value))
const canGoPrevious = computed(() => usersOffset.value > 0)
const canGoNext = computed(() => usersOffset.value + usersLimit.value < usersTotal.value)
const selectedActionUserName = computed(() => (
  selectedActionUser.value?.full_name || selectedActionUser.value?.username || selectedActionUser.value?.email || 'this user'
))
const userActionDialogTitle = computed(() => {
  if (pendingUserAction.value === 'reset-password') {
    return 'Reset user password'
  }
  if (selectedActionUser.value?.is_active) {
    return 'Deactivate user'
  }
  return 'Activate user'
})
const userActionDialogMessage = computed(() => {
  if (pendingUserAction.value === 'reset-password') {
    return `Reset the password for ${selectedActionUserName.value}?`
  }
  const action = selectedActionUser.value?.is_active ? 'Deactivate' : 'Activate'
  return `${action} ${selectedActionUserName.value}?`
})
const userActionWarning = computed(() => {
  if (pendingUserAction.value === 'reset-password') {
    return 'A new temporary password will be generated and must be shared securely.'
  }
  if (selectedActionUser.value?.is_active) {
    return 'The user will no longer be able to sign in while inactive.'
  }
  return 'The user will regain access according to their assigned roles.'
})
const userActionConfirmLabel = computed(() => {
  if (pendingUserAction.value === 'reset-password') {
    return 'Reset password'
  }
  return selectedActionUser.value?.is_active ? 'Deactivate user' : 'Activate user'
})
const userActionConfirmSeverity = computed(() => (
  pendingUserAction.value === 'toggle-active' && selectedActionUser.value?.is_active ? 'danger' : 'warn'
))

function resetDialogState(): void {
  dialogErrorMessage.value = null
  dialogSubmitting.value = false
}

async function loadData(): Promise<void> {
  loading.value = true
  pageErrorMessage.value = null
  try {
    const [usersResponse, rolesResponse] = await Promise.all([
      listUsers({ limit: usersLimit.value, offset: usersOffset.value }),
      listRoles(),
    ])
    users.value = usersResponse.items
    usersTotal.value = usersResponse.total
    usersLimit.value = usersResponse.limit
    usersOffset.value = usersResponse.offset
    roles.value = rolesResponse.items
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  } finally {
    loading.value = false
  }
}

async function loadPreviousUsers(): Promise<void> {
  usersOffset.value = Math.max(0, usersOffset.value - usersLimit.value)
  await loadData()
}

async function loadNextUsers(): Promise<void> {
  usersOffset.value += usersLimit.value
  await loadData()
}

function openCreateDialog(): void {
  resetDialogState()
  createForm.email = ''
  createForm.username = ''
  createForm.fullName = ''
  createForm.password = ''
  createForm.roleKeys = []
  createForm.forcePasswordChange = true
  createForm.isActive = true
  createDialogVisible.value = true
}

function openRolesDialog(user: AdminUserResponse): void {
  resetDialogState()
  selectedUser.value = user
  rolesForm.roleKeys = [...user.roles]
  rolesDialogVisible.value = true
}

function openActiveDialog(user: AdminUserResponse): void {
  resetDialogState()
  pageErrorMessage.value = null
  clearTemporaryPassword()
  selectedActionUser.value = user
  pendingUserAction.value = 'toggle-active'
  userActionDialogVisible.value = true
}

function openPasswordResetDialog(user: AdminUserResponse): void {
  resetDialogState()
  pageErrorMessage.value = null
  clearTemporaryPassword()
  selectedActionUser.value = user
  pendingUserAction.value = 'reset-password'
  userActionDialogVisible.value = true
}

function closeUserActionDialog(): void {
  userActionDialogVisible.value = false
  selectedActionUser.value = null
  pendingUserAction.value = null
}

async function confirmUserAction(): Promise<void> {
  const user = selectedActionUser.value
  const action = pendingUserAction.value
  if (user === null || action === null) {
    return
  }

  dialogSubmitting.value = true
  if (action === 'reset-password') {
    await resetPassword(user.id)
  } else {
    await toggleActive(user)
  }
  dialogSubmitting.value = false
  closeUserActionDialog()
}

async function submitCreateUser(): Promise<void> {
  resetDialogState()
  dialogSubmitting.value = true
  try {
    await createUser({
      email: createForm.email,
      username: createForm.username,
      full_name: createForm.fullName || null,
      password: createForm.password,
      is_active: createForm.isActive,
      role_keys: [...createForm.roleKeys],
      force_password_change: createForm.forcePasswordChange,
    })
    createDialogVisible.value = false
    await loadData()
  } catch (error) {
    dialogErrorMessage.value = asUserMessage(error)
  } finally {
    dialogSubmitting.value = false
  }
}

async function submitRoleUpdate(): Promise<void> {
  if (selectedUser.value === null) {
    return
  }

  resetDialogState()
  dialogSubmitting.value = true
  try {
    await replaceUserRoles(selectedUser.value.id, { role_keys: [...rolesForm.roleKeys] })
    rolesDialogVisible.value = false
    await loadData()
  } catch (error) {
    dialogErrorMessage.value = asUserMessage(error)
  } finally {
    dialogSubmitting.value = false
  }
}

async function toggleActive(user: AdminUserResponse): Promise<void> {
  pageErrorMessage.value = null
  try {
    await updateUser(user.id, { is_active: !user.is_active })
    await loadData()
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  }
}

async function resetPassword(userId: string): Promise<void> {
  pageErrorMessage.value = null
  clearTemporaryPassword()
  try {
    const response = await resetUserPassword(userId)
    await loadData()
    temporaryPasswordSecret.value = response.temporary_password
    temporaryPasswordRevealed.value = false
    temporaryPasswordCopyMessage.value = null
    temporaryPasswordDialogVisible.value = true
    scheduleTemporaryPasswordClear()
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  }
}

function scheduleTemporaryPasswordClear(): void {
  if (temporaryPasswordClearTimer !== null) {
    clearTimeout(temporaryPasswordClearTimer)
  }
  temporaryPasswordClearTimer = setTimeout(() => {
    clearTemporaryPassword()
  }, 60_000)
}

function clearTemporaryPassword(): void {
  if (temporaryPasswordClearTimer !== null) {
    clearTimeout(temporaryPasswordClearTimer)
    temporaryPasswordClearTimer = null
  }
  temporaryPasswordDialogVisible.value = false
  temporaryPasswordSecret.value = null
  temporaryPasswordRevealed.value = false
  temporaryPasswordCopyMessage.value = null
}

function revealTemporaryPassword(): void {
  if (temporaryPasswordSecret.value === null) {
    return
  }
  temporaryPasswordRevealed.value = true
}

async function copyTemporaryPassword(): Promise<void> {
  if (temporaryPasswordSecret.value === null) {
    return
  }

  try {
    await navigator.clipboard.writeText(temporaryPasswordSecret.value)
    temporaryPasswordCopyMessage.value = 'Temporary password copied. Close this dialog when you are done.'
  } catch {
    temporaryPasswordCopyMessage.value = 'Copy unavailable in this browser. Reveal the password and transfer it securely.'
  }
}

onMounted(async () => {
  await loadData()
})

onUnmounted(() => {
  clearTemporaryPassword()
})
</script>

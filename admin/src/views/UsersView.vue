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
    <Message v-if="temporaryPasswordMessage" severity="warn" :closable="false">
      {{ temporaryPasswordMessage }}
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
                <Button :label="slotProps.data.is_active ? 'Deactivate' : 'Activate'" size="small" severity="secondary" variant="outlined" @click="toggleActive(slotProps.data)" />
                <Button label="Reset password" size="small" severity="warn" variant="outlined" @click="resetPassword(slotProps.data.id)" />
              </div>
            </template>
          </Column>

          <template #empty>
            <div class="muted">No managed users have been created yet.</div>
          </template>
        </DataTable>
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
          <Password id="create-password" v-model="createForm.password" toggleMask :feedback="false" />
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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

const users = ref<AdminUserResponse[]>([])
const roles = ref<RoleResponse[]>([])
const loading = ref(false)
const pageErrorMessage = ref<string | null>(null)
const temporaryPasswordMessage = ref<string | null>(null)
const dialogErrorMessage = ref<string | null>(null)
const dialogSubmitting = ref(false)
const createDialogVisible = ref(false)
const rolesDialogVisible = ref(false)
const selectedUser = ref<AdminUserResponse | null>(null)

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

function resetDialogState(): void {
  dialogErrorMessage.value = null
  dialogSubmitting.value = false
}

async function loadData(): Promise<void> {
  loading.value = true
  pageErrorMessage.value = null
  temporaryPasswordMessage.value = null

  try {
    const [usersResponse, rolesResponse] = await Promise.all([listUsers(), listRoles()])
    users.value = usersResponse.items
    roles.value = rolesResponse.items
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  } finally {
    loading.value = false
  }
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
  temporaryPasswordMessage.value = null
  try {
    const response = await resetUserPassword(userId)
    await loadData()
    temporaryPasswordMessage.value = `Temporary password: ${response.temporary_password}`
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
  }
}

onMounted(async () => {
  await loadData()
})
</script>

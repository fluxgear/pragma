<template>
  <section class="page" aria-labelledby="roles-page-title">
    <div class="page__header">
      <div>
        <p class="eyebrow">People</p>
        <h1 id="roles-page-title">Roles administration</h1>
        <p class="muted">
          Review built-in product roles, inspect every backend permission, and create custom roles
          that combine only the permissions your operators need.
        </p>
      </div>
      <div class="inline-actions">
        <Button
          label="Refresh"
          icon="pi pi-refresh"
          severity="secondary"
          variant="outlined"
          :loading="loading"
          @click="loadRoles"
        />
        <Button
          label="New custom role"
          icon="pi pi-shield"
          :disabled="loading && !hasLoaded"
          @click="openCreateDialog"
        />
      </div>
    </div>

    <Message v-if="pageErrorMessage" severity="error" :closable="false">
      {{ pageErrorMessage }}
    </Message>

    <div v-if="loading && !hasLoaded" class="loading-state" role="status" aria-live="polite">
      Loading roles and permissions…
    </div>

    <div v-else-if="pageErrorMessage && roles.length === 0" class="error-state" role="alert">
      <strong>Roles could not be loaded.</strong>
      <p>Refresh the page or retry after the roles service is available.</p>
      <div class="inline-actions" style="justify-content: center;">
        <Button label="Retry" severity="secondary" variant="outlined" @click="loadRoles" />
      </div>
    </div>

    <div v-else-if="hasLoaded && roles.length === 0" class="empty-state">
      <strong>No roles returned by the backend.</strong>
      <p class="muted">
        Built-in system roles should always be present. Refresh after the backend seed data is available.
      </p>
    </div>

    <template v-else>
      <Card>
        <template #title>System role protection</template>
        <template #content>
          <Message severity="info" :closable="false">
            Built-in roles are read-only product roles. They can be assigned by user-management
            workflows, but this C2 slice does not expose edit or delete actions for any system role.
          </Message>
        </template>
      </Card>

      <section aria-labelledby="roles-list-title">
        <div class="page__header">
          <div>
            <h2 id="roles-list-title">Role definitions</h2>
            <p class="muted">
              {{ roles.length }} roles loaded. Custom roles can be created here; existing roles are displayed read-only.
            </p>
          </div>
        </div>

        <div class="page__grid">
          <Card v-for="role in roles" :key="role.role_key">
            <template #title>
              <div class="status-row">
                <span>{{ role.name }}</span>
                <Tag :severity="role.is_system ? 'info' : 'success'" :value="role.is_system ? 'System' : 'Custom'" />
              </div>
            </template>
            <template #content>
              <div class="form-stack">
                <div class="field">
                  <span class="muted">Role key</span>
                  <code class="code-chip">{{ role.role_key }}</code>
                </div>
                <p class="muted">
                  {{ role.description || 'No description provided.' }}
                </p>
                <Message v-if="role.is_system" severity="info" :closable="false">
                  Read-only system role. No edit or delete controls are available.
                </Message>
                <div class="field">
                  <span class="muted">Granted permissions</span>
                  <div v-if="role.permission_keys.length > 0" class="content-workspace__field-summary" :aria-label="`${role.name} granted permissions`">
                    <Tag
                      v-for="permissionKey in role.permission_keys"
                      :key="`${role.role_key}-${permissionKey}`"
                      severity="secondary"
                      :value="permissionLabel(permissionKey)"
                    />
                  </div>
                  <span v-else class="muted">No permissions granted.</span>
                </div>
              </div>
            </template>
          </Card>
        </div>
      </section>

      <section aria-labelledby="permission-catalog-title">
        <div class="page__header">
          <div>
            <h2 id="permission-catalog-title">Permission catalog</h2>
            <p class="muted">
              Backend-provided permission definitions grouped by domain. These definitions also drive the custom-role checklist.
            </p>
          </div>
        </div>

        <div v-if="permissionGroups.length === 0" class="empty-state">
          No permission definitions were returned by the backend.
        </div>
        <div v-else class="page__grid">
          <Card v-for="group in permissionGroups" :key="group.domain">
            <template #title>{{ group.domain }}</template>
            <template #content>
              <div class="form-stack">
                <div v-for="permission in group.permissions" :key="permission.key" class="field">
                  <strong>{{ permission.name }}</strong>
                  <code class="code-chip">{{ permission.key }}</code>
                  <small class="muted">{{ permission.description || 'No description provided.' }}</small>
                </div>
              </div>
            </template>
          </Card>
        </div>
      </section>
    </template>

    <Dialog
      v-model:visible="createDialogVisible"
      modal
      :draggable="false"
      :closable="!dialogSubmitting"
      :style="{ width: 'min(48rem, 95vw)' }"
      header="Create a custom role"
      @hide="resetCreateForm"
    >
      <form class="form-stack" @submit.prevent="submitCreateRole">
        <Message v-if="dialogErrorMessage" severity="error" :closable="false" role="alert">
          {{ dialogErrorMessage }}
        </Message>

        <div class="form-grid">
          <div class="field">
            <label for="create-role-key">Role key</label>
            <InputText
              id="create-role-key"
              v-model.trim="createForm.roleKey"
              required
              autocomplete="off"
              aria-describedby="create-role-key-help"
              placeholder="regional_editor"
            />
            <small id="create-role-key-help" class="muted">
              Use a stable lowercase key such as regional_editor. Backend validation rejects duplicate or system keys.
            </small>
          </div>

          <div class="field">
            <label for="create-role-name">Name</label>
            <InputText
              id="create-role-name"
              v-model.trim="createForm.name"
              required
              autocomplete="off"
              placeholder="Regional Editor"
            />
          </div>

          <div class="field field--full">
            <label for="create-role-description">Description</label>
            <Textarea
              id="create-role-description"
              v-model.trim="createForm.description"
              rows="3"
              autoResize
              placeholder="Describe what this role is allowed to manage."
            />
          </div>
        </div>

        <fieldset class="field">
          <legend>Permissions</legend>
          <small class="muted">
            Select backend permission keys for this custom role. {{ selectedPermissionCount }} selected.
          </small>

          <div v-if="permissionGroups.length === 0" class="empty-state">
            No permissions are available to select. Refresh the roles catalog before creating a custom role.
          </div>

          <div v-else class="form-stack">
            <Card v-for="group in permissionGroups" :key="`dialog-${group.domain}`">
              <template #title>{{ group.domain }}</template>
              <template #content>
                <div class="form-stack">
                  <label
                    v-for="permission in group.permissions"
                    :key="`select-${permission.key}`"
                    class="field__checkbox-row"
                  >
                    <input
                      type="checkbox"
                      :data-testid="`permission-checkbox-${permission.key}`"
                      :checked="isPermissionSelected(permission.key)"
                      @change="handlePermissionCheckbox(permission.key, $event)"
                    >
                    <span>
                      <strong>{{ permission.name }}</strong>
                      <span class="muted code-chip">{{ permission.key }}</span>
                    </span>
                  </label>
                </div>
              </template>
            </Card>
          </div>
        </fieldset>

        <div class="inline-actions">
          <Button
            label="Cancel"
            type="button"
            severity="secondary"
            variant="outlined"
            :disabled="dialogSubmitting"
            @click="closeCreateDialog"
          />
          <Button
            label="Create custom role"
            icon="pi pi-check"
            type="submit"
            :loading="dialogSubmitting"
          />
        </div>
      </form>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import { ApiClientError, asUserMessage } from '@/api/errors'
import { createRole, listRolesAdmin } from '@/api/roles'
import type { PermissionDefinitionResponse, RoleResponse } from '@/api/types'

interface PermissionDomainGroup {
  domain: string
  permissions: PermissionDefinitionResponse[]
}

const roles = ref<RoleResponse[]>([])
const permissionDefinitions = ref<PermissionDefinitionResponse[]>([])
const loading = ref(false)
const hasLoaded = ref(false)
const pageErrorMessage = ref<string | null>(null)
const createDialogVisible = ref(false)
const dialogSubmitting = ref(false)
const dialogErrorMessage = ref<string | null>(null)

const createForm = reactive({
  roleKey: '',
  name: '',
  description: '',
  permissionKeys: [] as string[],
})

const permissionLookup = computed(() => {
  return new Map(permissionDefinitions.value.map((permission) => [permission.key, permission]))
})

const permissionGroups = computed<PermissionDomainGroup[]>(() => {
  const grouped = new Map<string, PermissionDefinitionResponse[]>()

  for (const permission of permissionDefinitions.value) {
    const domainPermissions = grouped.get(permission.domain) ?? []
    domainPermissions.push(permission)
    grouped.set(permission.domain, domainPermissions)
  }

  return Array.from(grouped.entries())
    .sort(([leftDomain], [rightDomain]) => leftDomain.localeCompare(rightDomain))
    .map(([domain, permissions]) => ({
      domain,
      permissions: [...permissions].sort((left, right) => left.key.localeCompare(right.key)),
    }))
})

const selectedPermissionCount = computed(() => createForm.permissionKeys.length)

function permissionLabel(permissionKey: string): string {
  const definition = permissionLookup.value.get(permissionKey)
  return definition ? `${definition.name} (${permissionKey})` : permissionKey
}

async function loadRoles(): Promise<void> {
  loading.value = true
  pageErrorMessage.value = null

  try {
    const response = await listRolesAdmin()
    roles.value = response.items
    permissionDefinitions.value = response.permission_definitions
    hasLoaded.value = true
  } catch (error) {
    pageErrorMessage.value = asUserMessage(error)
    hasLoaded.value = true
  } finally {
    loading.value = false
  }
}

function resetCreateForm(): void {
  createForm.roleKey = ''
  createForm.name = ''
  createForm.description = ''
  createForm.permissionKeys = []
  dialogErrorMessage.value = null
}

function openCreateDialog(): void {
  resetCreateForm()
  createDialogVisible.value = true
}

function closeCreateDialog(): void {
  if (dialogSubmitting.value) {
    return
  }

  createDialogVisible.value = false
  resetCreateForm()
}

function isPermissionSelected(permissionKey: string): boolean {
  return createForm.permissionKeys.includes(permissionKey)
}

function handlePermissionCheckbox(permissionKey: string, event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) {
    return
  }

  if (target.checked && !createForm.permissionKeys.includes(permissionKey)) {
    createForm.permissionKeys.push(permissionKey)
    return
  }

  if (!target.checked) {
    createForm.permissionKeys = createForm.permissionKeys.filter((selectedKey) => selectedKey !== permissionKey)
  }
}

function createErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === 'ROLE_KEY_CONFLICT') {
      return `A role with this key already exists. ${error.detail}`
    }

    if (error.code === 'ROLE_SYSTEM_KEY_CONFLICT') {
      return `That role key is reserved for a built-in system role. ${error.detail}`
    }

    if (error.code === 'ROLE_PERMISSION_INVALID') {
      return `One or more selected permissions are invalid. ${error.detail}`
    }
  }

  return asUserMessage(error)
}

async function submitCreateRole(): Promise<void> {
  dialogErrorMessage.value = null

  const roleKey = createForm.roleKey.trim()
  const name = createForm.name.trim()

  if (!roleKey || !name) {
    dialogErrorMessage.value = 'Role key and name are required.'
    return
  }

  dialogSubmitting.value = true

  try {
    await createRole({
      role_key: roleKey,
      name,
      description: createForm.description.trim() || null,
      permission_keys: [...createForm.permissionKeys],
    })
    await loadRoles()
    createDialogVisible.value = false
    resetCreateForm()
  } catch (error) {
    dialogErrorMessage.value = createErrorMessage(error)
  } finally {
    dialogSubmitting.value = false
  }
}

onMounted(async () => {
  await loadRoles()
})
</script>

<template>
  <a class="skip-link" href="#admin-main">Skip to main content</a>
  <div class="shell">
    <Toolbar class="shell__toolbar" aria-label="Admin workspace header">
      <template #start>
        <div class="shell__toolbar-start">
          <div class="shell__brand" aria-label="Pragma Admin">
            <span class="shell__brand-mark" aria-hidden="true">P</span>
            <div class="shell__brand-copy">
              <strong>Pragma Admin</strong>
              <span>Commercial CMS workbench</span>
            </div>
          </div>
          <div class="shell__status-strip" aria-label="Workspace status">
            <Tag severity="success" value="Installed" />
            <Tag :severity="realtimeTagSeverity" :value="realtimeTagLabel" />
          </div>
        </div>
      </template>
      <template #end>
        <div class="shell__toolbar-end">
          <div class="shell__user-card">
            <span class="shell__user-email">{{ user?.email }}</span>
            <span class="shell__user-role">{{ roleBadge }}</span>
          </div>
          <Tag v-if="requiresPasswordChange" severity="warn" value="Password change required" />
          <Button icon="pi pi-sign-out" label="Logout" severity="secondary" aria-label="Logout" @click="handleLogout" />
        </div>
      </template>
    </Toolbar>

    <div class="shell__body">
      <aside class="shell__nav" aria-label="Admin navigation">
        <details class="shell__nav-drawer" :open="isNavigationOpen" @toggle="handleNavigationToggle">
          <summary class="shell__nav-summary">
            <span>Navigation</span>
            <span class="muted">{{ activeSectionLabel }}</span>
          </summary>

          <nav class="shell__nav-groups" aria-label="Admin sections">
            <section
              v-for="group in navigationGroups"
              :key="group.id"
              class="shell__nav-section"
              :aria-labelledby="`nav-section-${group.id}`"
            >
              <div class="shell__nav-section-header">
                <span :id="`nav-section-${group.id}`" class="shell__nav-section-title">{{ group.label }}</span>
                <span class="shell__nav-section-description">{{ group.description }}</span>
              </div>

              <div class="shell__nav-list">
                <button
                  v-for="item in group.items"
                  :key="`${group.id}-${item.label}`"
                  type="button"
                  class="shell__nav-link"
                  :class="{
                    'shell__nav-link--active': isActiveNavigationItem(item),
                    'shell__nav-link--disabled': item.disabled,
                  }"
                  :disabled="item.disabled"
                  :aria-current="isActiveNavigationItem(item) ? 'page' : undefined"
                  :aria-disabled="item.disabled ? 'true' : undefined"
                  :title="item.disabledReason"
                  @click="item.routeName !== null && navigate(item.routeName)"
                >
                  <span :class="['shell__nav-link-icon', item.icon]" aria-hidden="true" />
                  <span class="shell__nav-link-copy">
                    <span class="shell__nav-link-label">{{ item.label }}</span>
                    <span class="shell__nav-link-description">{{ item.description }}</span>
                  </span>
                  <span v-if="item.badge" class="shell__nav-link-badge">{{ item.badge }}</span>
                </button>
              </div>
            </section>
          </nav>
        </details>
      </aside>

      <main id="admin-main" class="shell__main" tabindex="-1">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Toolbar from 'primevue/toolbar'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useRealtimeStore } from '@/stores/realtime'

interface NavigationItemDefinition {
  label: string
  description: string
  icon: string
  routeName: string | null
  permission?: string
}

interface NavigationItem extends NavigationItemDefinition {
  disabled: boolean
  badge: string | null
  disabledReason: string | undefined
}

interface NavigationGroup {
  id: string
  label: string
  description: string
  items: NavigationItem[]
}

function visibleGroups(groups: NavigationGroup[]): NavigationGroup[] {
  return groups.filter((group) => group.items.length > 0)
}

const authStore = useAuthStore()
const realtimeStore = useRealtimeStore()
const { user, requiresPasswordChange, isAuthenticated } = storeToRefs(authStore)
const { connectionState } = storeToRefs(realtimeStore)
const route = useRoute()
const router = useRouter()
const isCompactNavigation = ref(false)
const isNavigationOpen = ref(true)
let compactNavigationQuery: MediaQueryList | undefined

const roleBadge = computed(() => {
  if (user.value?.is_superuser) {
    return 'Super-admin'
  }
  if (user.value?.roles.length) {
    return user.value.roles.join(', ')
  }
  return 'User'
})

const realtimeTagLabel = computed(() => {
  switch (connectionState.value) {
    case 'live':
      return 'Live'
    case 'connecting':
      return 'Connecting'
    case 'reconnecting':
      return 'Reconnecting'
    default:
      return 'Offline'
  }
})

const realtimeTagSeverity = computed(() => {
  switch (connectionState.value) {
    case 'live':
      return 'success'
    case 'connecting':
      return 'info'
    case 'reconnecting':
      return 'warn'
    default:
      return 'secondary'
  }
})

const navigationGroups = computed<NavigationGroup[]>(() => visibleGroups([
  {
    id: 'workspace',
    label: 'Workspace',
    description: 'Current session',
    items: [
      navigationItem({
        label: 'Dashboard',
        description: 'Health, identity, and readiness',
        icon: 'pi pi-home',
        routeName: 'dashboard',
      }),
    ],
  },
  {
    id: 'content',
    label: 'Content',
    description: 'Editorial inventory',
    items: [
      navigationItem({
        label: 'Content entries',
        description: 'Author and manage entries',
        icon: 'pi pi-file-edit',
        routeName: 'content',
        permission: 'content.entries.read',
      }),
      navigationItem({
        label: 'Content models',
        description: 'Field schemas and types',
        icon: 'pi pi-sitemap',
        routeName: 'content-models',
        permission: 'content.types.read',
      }),
    ],
  },
  {
    id: 'structure',
    label: 'Structure',
    description: 'Site architecture',
    items: [
      navigationItem({
        label: 'Navigation menus',
        description: 'Primary public menu',
        icon: 'pi pi-list',
        routeName: 'navigation',
        permission: 'navigation.manage',
      }),
    ],
  },
  {
    id: 'design',
    label: 'Design',
    description: 'Theme and presentation',
    items: [
      ...(authStore.hasPermission('themes.manage')
        ? [
            navigationItem({
              label: 'Theme design',
              description: 'Installed themes and safe design tokens',
              icon: 'pi pi-palette',
              routeName: 'themes',
              permission: 'themes.manage',
            }),
          ]
        : []),
    ],
  },
  {
    id: 'assets',
    label: 'Assets',
    description: 'Files and media',
    items: [
      navigationItem({
        label: 'Media library',
        description: 'Upload, browse, and delete assets',
        icon: 'pi pi-images',
        routeName: 'media',
        permission: 'media.assets.read',
      }),
    ],
  },
  {
    id: 'people',
    label: 'People',
    description: 'Users and access',
    items: [
      navigationItem({
        label: 'Users',
        description: 'Accounts and role assignment',
        icon: 'pi pi-users',
        routeName: 'users',
        permission: 'users.manage',
      }),
      navigationItem({
        label: 'Roles',
        description: 'Create and review admin roles',
        icon: 'pi pi-id-card',
        routeName: 'roles',
        permission: 'roles.manage',
      }),
      navigationItem({
        label: 'Account',
        description: 'Your profile and password',
        icon: 'pi pi-user',
        routeName: 'account',
      }),
    ],
  },
  {
    id: 'extensions',
    label: 'Extensions',
    description: 'Runtime capabilities',
    items: [
      navigationItem({
        label: 'Modules',
        description: 'Enable or disable modules',
        icon: 'pi pi-box',
        routeName: 'modules',
        permission: 'modules.manage',
      }),
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    description: 'Platform configuration',
    items: [
      navigationItem({
        label: 'AI settings',
        description: 'Semantic provider configuration',
        icon: 'pi pi-sparkles',
        routeName: 'ai-settings',
        permission: 'ai.settings.manage',
      }),
    ],
  },
  {
    id: 'observability',
    label: 'Observability',
    description: 'Operational history',
    items: [
      navigationItem({
        label: 'Activity log',
        description: 'Audit and workflow events',
        icon: 'pi pi-history',
        routeName: null,
      }),
    ],
  },
]))

const activeSectionLabel = computed(() => {
  const activeGroup = navigationGroups.value.find((group) => group.items.some(isActiveNavigationItem))
  return activeGroup?.label ?? 'Workspace'
})

function navigationItem(item: NavigationItemDefinition): NavigationItem {
  const permissionDenied = item.permission !== undefined && !authStore.hasPermission(item.permission)
  const isComingLater = item.routeName === null
  const disabled = isComingLater || permissionDenied

  return {
    ...item,
    disabled,
    badge: isComingLater ? 'Later' : permissionDenied ? 'Locked' : null,
    disabledReason: disabledReasonFor(item, isComingLater, permissionDenied),
  }
}

function disabledReasonFor(
  item: NavigationItemDefinition,
  isComingLater: boolean,
  permissionDenied: boolean,
): string | undefined {
  if (isComingLater) {
    return `${item.label} is planned for a later commercial workflow.`
  }
  if (permissionDenied && item.permission !== undefined) {
    return `Requires ${item.permission}.`
  }
  return undefined
}

function isActiveNavigationItem(item: NavigationItem): boolean {
  return item.routeName !== null && route.name === item.routeName
}

function syncNavigationMode(matchesCompactNavigation: boolean): void {
  isCompactNavigation.value = matchesCompactNavigation
  isNavigationOpen.value = !matchesCompactNavigation
}

function handleNavigationViewportChange(event: MediaQueryListEvent): void {
  syncNavigationMode(event.matches)
}

function handleNavigationToggle(event: Event): void {
  isNavigationOpen.value = (event.target as HTMLDetailsElement).open
}

watch(
  [isAuthenticated, requiresPasswordChange],
  ([authenticated, passwordChangeRequired]) => {
    if (authenticated && !passwordChangeRequired) {
      realtimeStore.start()
      return
    }
    realtimeStore.stop()
  },
  { immediate: true },
)

onMounted(() => {
  if (typeof window !== 'undefined' && 'matchMedia' in window) {
    compactNavigationQuery = window.matchMedia('(max-width: 960px)')
    syncNavigationMode(compactNavigationQuery.matches)
    compactNavigationQuery.addEventListener('change', handleNavigationViewportChange)
  }

  if (isAuthenticated.value && !requiresPasswordChange.value) {
    realtimeStore.start()
  }
})

onUnmounted(() => {
  compactNavigationQuery?.removeEventListener('change', handleNavigationViewportChange)
  realtimeStore.stop()
})

function navigate(routeName: string): void {
  if (isCompactNavigation.value) {
    isNavigationOpen.value = false
  }

  if (route.name !== routeName) {
    void router.push({ name: routeName })
  }
}

async function handleLogout(): Promise<void> {
  realtimeStore.stop()
  await authStore.logout()
  await router.push({ name: 'login' })
}
</script>

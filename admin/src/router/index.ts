import { createRouter, createWebHistory } from 'vue-router'

import AppShellLayout from '@/layouts/AppShellLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import { resolveNavigation } from '@/router/guards'
import { useAuthStore } from '@/stores/auth'
import { useInstallStore } from '@/stores/install'
const AccountView = () => import('@/views/AccountView.vue')
const AiSettingsView = () => import('@/views/AiSettingsView.vue')
const BootView = () => import('@/views/BootView.vue')
const ContentEntriesView = () => import('@/views/ContentEntriesView.vue')
const ContentModelsView = () => import('@/views/ContentModelsView.vue')
const DashboardView = () => import('@/views/DashboardView.vue')
const NavigationView = () => import('@/views/NavigationView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const MediaLibraryView = () => import('@/views/MediaLibraryView.vue')
const NotFoundView = () => import('@/views/NotFoundView.vue')
const SetupWizardView = () => import('@/views/SetupWizardView.vue')
const UsersView = () => import('@/views/UsersView.vue')
const ModulesView = () => import('@/views/ModulesView.vue')
const RolesView = () => import('@/views/RolesView.vue')
const ThemesView = () => import('@/views/ThemesView.vue')
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: BootView,
      meta: { title: 'Loading' },
    },
    {
      path: '/login',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'login',
          component: LoginView,
          meta: { guestOnly: true, title: 'Sign in' },
        },
      ],
    },
    {
      path: '/setup',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'setup',
          component: SetupWizardView,
          meta: { title: 'Setup wizard' },
        },
      ],
    },
    {
      path: '/app',
      component: AppShellLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: DashboardView,
          meta: { requiresAuth: true, title: 'Dashboard' },
        },
        {
          path: 'content',
          name: 'content',
          component: ContentEntriesView,
          meta: {
            requiresAuth: true,
            requiresPermission: 'content.entries.read',
            title: 'Content entries',
          },
        },
        {
          path: 'content-models',
          name: 'content-models',
          component: ContentModelsView,
          meta: {
            requiresAuth: true,
            requiresPermission: 'content.types.read',
            title: 'Content models',
          },
        },
        {
          path: 'media',
          name: 'media',
          component: MediaLibraryView,
          meta: {
            requiresAuth: true,
            requiresPermission: 'media.assets.read',
            title: 'Media library',
          },
        },
        {
          path: 'ai',
          name: 'ai-settings',
          component: AiSettingsView,
          meta: {
            requiresAuth: true,
            requiresPermission: 'ai.settings.manage',
            title: 'AI settings',
          },
        },
        {
          path: 'themes',
          name: 'themes',
          component: ThemesView,
          meta: {
            requiresAuth: true,
            requiresPermission: 'themes.manage',
            title: 'Themes',
          },
        },
        {
          path: 'navigation',
          name: 'navigation',
          component: NavigationView,
          meta: {
            requiresAuth: true,
            requiresPermission: 'navigation.manage',
            title: 'Navigation',
          },
        },
        {
          path: 'users',
          name: 'users',
          component: UsersView,
          meta: { requiresAuth: true, requiresPermission: 'users.manage', title: 'Users' },
        },
        {
          path: 'roles',
          name: 'roles',
          component: RolesView,
          meta: { requiresAuth: true, requiresPermission: 'roles.manage', title: 'Roles' },
        },
        {
          path: 'modules',
          name: 'modules',
          component: ModulesView,
          meta: { requiresAuth: true, requiresPermission: 'modules.manage', title: 'Modules' },
        },
        {
          path: 'account',
          name: 'account',
          component: AccountView,
          meta: { requiresAuth: true, allowForcedPasswordChange: true, title: 'Account' },
        },
        {
          path: ':pathMatch(.*)*',
          name: 'app-not-found',
          component: NotFoundView,
          meta: { requiresAuth: true, title: 'Not found' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: NotFoundView,
      meta: { title: 'Not found' },
    },
  ],
})

router.beforeEach(async (to) => {
  const installStore = useInstallStore()
  const authStore = useAuthStore()

  return resolveNavigation(
    {
      name: to.name,
      fullPath: to.fullPath,
      meta: to.meta,
    },
    installStore,
    authStore,
  )
})
router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? `${to.meta.title} · Pragma Admin` : 'Pragma Admin'
  document.title = title
})

import { createRouter, createWebHistory } from 'vue-router'

import AppShellLayout from '@/layouts/AppShellLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import { evaluateNavigation } from '@/router/guards'
import { useAuthStore } from '@/stores/auth'
import { useInstallStore } from '@/stores/install'
import BootView from '@/views/BootView.vue'
import DashboardView from '@/views/DashboardView.vue'
import LoginView from '@/views/LoginView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import SetupWizardView from '@/views/SetupWizardView.vue'

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
          path: ':pathMatch(.*)*',
          name: 'app-not-found',
          component: NotFoundView,
          meta: { requiresAuth: true, title: 'Not found' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'home' },
    },
  ],
})

router.beforeEach(async (to) => {
  const installStore = useInstallStore()
  const authStore = useAuthStore()

  await installStore.ensureStatus()
  await authStore.ensureInitialized(installStore.isInstalled)

  return evaluateNavigation(
    {
      name: to.name,
      fullPath: to.fullPath,
      meta: to.meta,
    },
    {
      isInstalled: installStore.isInstalled,
      isAuthenticated: authStore.isAuthenticated,
    },
  )
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? `${to.meta.title} · Pragma Admin` : 'Pragma Admin'
  document.title = title
})

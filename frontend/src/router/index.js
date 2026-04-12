import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { guest: true } },
  { path: '/auth/callback', name: 'AuthCallback', component: () => import('../views/AuthCallback.vue'), meta: { guest: true } },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'analytics', name: 'Analytics', component: () => import('../views/Analytics.vue') },
      { path: 'alerts', name: 'Alerts', component: () => import('../views/Alerts.vue') },
      { path: 'forecast', name: 'Forecast', component: () => import('../views/Forecast.vue') },
      { path: 'projects', name: 'Projects', component: () => import('../views/Projects.vue') },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) return next('/login')
  if (to.meta.guest && token) return next('/')
  next()
})

export default router

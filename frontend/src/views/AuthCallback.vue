<template>
  <div class="min-h-screen bg-void flex items-center justify-center">
    <p class="text-muted">{{ status }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { auth as authApi } from '../api/client'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const authStore = useAuthStore()
const status = ref('Вход...')

onMounted(async () => {
  const code = route.query.code
  const state = route.query.state
  if (!code) {
    status.value = 'Нет кода авторизации'
    return
  }
  if (!state) {
    status.value = 'Нет state; повторите вход'
    return
  }
  try {
    const data = await authApi.callback(code, state)
    authStore.setAuth(data.access_token, data.user)
    window.location.replace('/')
  } catch (e) {
    const msg = e.response?.data?.detail ?? e.message ?? 'Ошибка входа'
    status.value = typeof msg === 'string' ? msg : 'Ошибка входа'
  }
})
</script>

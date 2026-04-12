<template>
  <div class="min-h-screen bg-void flex flex-col">
    <header class="border-b border-border bg-surface/80 backdrop-blur sticky top-0 z-10 animate-fade-in">
      <div class="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <router-link to="/" class="font-display font-semibold text-lg text-gray-100 tracking-tight">
          EcomProfit Guard
        </router-link>
        <nav class="flex items-center gap-6">
          <router-link
            v-for="item in nav"
            :key="item.path + item.label"
            :to="item.path"
            class="text-sm text-gray-400 hover:text-accent transition-colors duration-200"
            active-class="text-accent"
          >
            {{ item.label }}
          </router-link>
          <div class="flex items-center gap-3 pl-4 border-l border-border">
            <span class="text-sm text-muted" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ auth.userName }}</span>
            <button
              type="button"
              class="text-sm text-muted hover:text-gray-200 transition-colors"
              @click="logout"
            >
              Выход
            </button>
          </div>
        </nav>
      </div>
    </header>
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 py-8">
      <router-view v-slot="{ Component }">
        <transition name="slide" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { usePrivacyStore } from '../stores/privacy'
import { useAppConfigStore } from '../stores/appConfig'

const auth = useAuthStore()
const privacy = usePrivacyStore()
const appConfig = useAppConfigStore()

onMounted(() => appConfig.fetch())

const nav = computed(() => [
  { path: '/', label: 'Дашборд' },
  { path: '/analytics', label: 'Аналитика' },
  { path: '/alerts', label: 'Алерты' },
  { path: '/forecast', label: 'Прогноз ИИ' },
  { path: '/projects', label: appConfig.staticProjectEnabled ? 'Синхронизация' : 'Проекты' },
])

function logout() {
  auth.logout()
  window.location.href = '/login'
}
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>

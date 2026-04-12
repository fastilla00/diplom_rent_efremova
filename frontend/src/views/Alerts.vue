<template>
  <div class="animate-fade-in">
    <div class="flex items-center justify-between mb-8">
      <h1 class="font-display text-2xl font-semibold text-gray-100">Алерты</h1>
      <div class="flex items-center gap-3">
        <select
          v-if="!appConfig.staticProjectEnabled"
          v-model="projectId"
          class="bg-surface border border-border rounded-lg px-4 py-2 text-sm"
          @change="load"
        >
          <option :value="null">Проект</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ projectLabel(p) }}</option>
        </select>
        <button
          class="px-4 py-2 bg-accent text-void rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          :disabled="!projectId || computing"
          @click="compute"
        >
          {{ computing ? 'Расчёт...' : 'Пересчитать алерты' }}
        </button>
      </div>
    </div>
    <div v-if="!projectId" class="text-muted py-16 text-center">Выберите проект</div>
    <div v-else-if="loading" class="text-muted py-16 text-center">Загрузка...</div>
    <ul v-else class="space-y-4">
      <li
        v-for="a in alerts"
        :key="a.id"
        class="bg-surface border rounded-xl p-5 border-l-4 animate-slide-up"
        :class="a.severity === 'high' ? 'border-danger' : 'border-warning'"
      >
        <div class="flex justify-between items-start">
          <div :class="{ 'privacy-sensitive': privacy.blurSensitive }">
            <p class="font-medium text-gray-100">{{ a.title }}</p>
            <p class="text-sm text-muted mt-1">{{ a.message }}</p>
            <p v-if="a.recommendation" class="text-sm text-accent mt-2">{{ a.recommendation }}</p>
          </div>
          <span
            class="text-xs px-2 py-1 rounded"
            :class="a.severity === 'high' ? 'bg-danger/20 text-danger' : 'bg-warning/20 text-warning'"
          >
            {{ a.severity === 'high' ? 'Высокий' : 'Средний' }}
          </span>
        </div>
        <p class="text-xs text-muted mt-2">{{ formatDate(a.created_at) }}</p>
      </li>
      <li v-if="alerts.length === 0" class="text-muted text-center py-12">Нет алертов</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { projects as projectsApi, alertsApi } from '../api/client'
import { usePrivacyStore } from '../stores/privacy'
import { useAppConfigStore } from '../stores/appConfig'

const privacy = usePrivacyStore()
const appConfig = useAppConfigStore()
const projects = ref([])
const projectId = ref(null)
const loading = ref(false)
const computing = ref(false)
const alerts = ref([])

function formatDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleString('ru-RU')
}

function projectLabel(p) {
  if (!p) return ''
  return privacy.blurSensitive ? `Проект №${p.id}` : p.name
}

async function loadProjects() {
  projects.value = await projectsApi.list()
  if (projects.value.length && !projectId.value) projectId.value = projects.value[0].id
}
async function load() {
  if (!projectId.value) return
  loading.value = true
  try {
    alerts.value = await alertsApi.list(projectId.value)
  } finally {
    loading.value = false
  }
}
async function compute() {
  if (!projectId.value) return
  computing.value = true
  try {
    await alertsApi.compute(projectId.value)
    await load()
  } finally {
    computing.value = false
  }
}
watch(projectId, load)

onMounted(async () => {
  await appConfig.fetch()
  await loadProjects()
})
</script>

<template>
  <div class="animate-fade-in">
    <div class="flex items-center justify-between mb-8">
      <h1 class="font-display text-2xl font-semibold text-gray-100">Дашборд</h1>
      <div class="flex items-center gap-3">
        <select
          v-if="!appConfig.staticProjectEnabled"
          v-model="projectId"
          class="bg-surface border border-border rounded-lg px-4 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-accent/30"
          @change="load"
        >
          <option :value="null">Выберите проект</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ projectLabel(p) }}</option>
        </select>
        <input
          v-model="periodStart"
          type="date"
          class="bg-surface border border-border rounded-lg px-3 py-2 text-sm"
          @change="load"
        />
        <span class="text-muted">—</span>
        <input
          v-model="periodEnd"
          type="date"
          class="bg-surface border border-border rounded-lg px-3 py-2 text-sm"
          @change="load"
        />
      </div>
    </div>
    <div v-if="!projectId" class="text-muted text-center py-16">Выберите проект</div>
    <div v-else-if="loading" class="text-muted text-center py-16">Загрузка...</div>
    <template v-else-if="data">
      <p
        v-if="data.summary && Number(data.summary.revenue) === 0 && Number(data.summary.costs) === 0"
        class="text-muted text-sm mb-4"
      >
        Данных нет. Откройте раздел «{{ appConfig.staticProjectEnabled ? 'Синхронизация' : 'Проекты' }}» и нажмите «Синхронизировать».
      </p>
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <div
          v-for="(v, k) in summaryCards"
          :key="k"
          class="bg-surface border border-border rounded-xl p-5 animate-slide-up"
          :style="{ animationDelay: `${k * 0.05}s` }"
        >
          <p class="text-muted text-xs uppercase tracking-wider mb-1">{{ v.label }}</p>
          <p class="text-xl font-semibold text-gray-100">{{ v.value }}</p>
        </div>
      </div>
      <div class="grid md:grid-cols-3 gap-6">
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">Топ проектов по выручке</h3>
          <ul class="space-y-2">
            <li
              v-for="(item, i) in data.top_projects"
              :key="i"
              class="flex justify-between text-sm"
            >
              <span class="text-gray-300 truncate mr-2" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ item.name }}</span>
              <span class="text-accent font-mono">{{ formatMoney(item.value) }}</span>
            </li>
          </ul>
        </div>
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">Топ специалистов</h3>
          <ul class="space-y-2">
            <li
              v-for="(item, i) in data.top_specialists"
              :key="i"
              class="flex justify-between text-sm"
            >
              <span class="text-gray-300 truncate mr-2" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ item.name }}</span>
              <span class="text-accent font-mono">{{ formatMoney(item.value) }}</span>
            </li>
          </ul>
        </div>
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">По подразделениям</h3>
          <ul class="space-y-2">
            <li
              v-for="(item, i) in data.by_department"
              :key="i"
              class="flex justify-between text-sm"
            >
              <span class="text-gray-300 truncate mr-2" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ item.name }}</span>
              <span class="text-accent font-mono">{{ formatMoney(item.value) }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { projects as projectsApi, dashboard as dashboardApi } from '../api/client'
import { usePrivacyStore } from '../stores/privacy'
import { useAppConfigStore } from '../stores/appConfig'

const privacy = usePrivacyStore()
const appConfig = useAppConfigStore()
const projects = ref([])
const projectId = ref(null)
const periodStart = ref('')
const periodEnd = ref('')
const loading = ref(false)
const data = ref(null)

const summaryCards = computed(() => {
  if (!data.value?.summary) return []
  const s = data.value.summary
  return [
    { label: 'Выручка', value: formatMoney(s.revenue) },
    { label: 'Затраты', value: formatMoney(s.costs) },
    { label: 'Прибыль', value: formatMoney(s.profit) },
    { label: 'Рентабельность', value: s.profitability_pct != null ? `${s.profitability_pct.toFixed(1)}%` : '—' },
    { label: 'Клиентов', value: s.unique_clients },
    { label: 'Специалистов', value: s.unique_specialists },
  ]
})

function formatMoney(v) {
  if (v == null) return '—'
  return new Intl.NumberFormat('ru-RU', { style: 'decimal', maximumFractionDigits: 0 }).format(Number(v)) + ' ₽'
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
  data.value = null
  try {
    data.value = await dashboardApi.get(projectId.value, {
      period_start: periodStart.value || undefined,
      period_end: periodEnd.value || undefined,
    })
  } catch (e) {
    data.value = { summary: {}, top_projects: [], top_specialists: [], by_department: [] }
  } finally {
    loading.value = false
  }
}

watch(projectId, load)
const d = new Date()
periodEnd.value = d.toISOString().slice(0, 10)
periodStart.value = new Date(d.getFullYear(), d.getMonth() - 11, 1).toISOString().slice(0, 10)

onMounted(async () => {
  await appConfig.fetch()
  await loadProjects()
})
</script>

<template>
  <div class="animate-fade-in">
    <div class="flex items-center justify-between mb-8">
      <h1 class="font-display text-2xl font-semibold text-gray-100">Аналитика</h1>
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
        <select v-model="groupBy" class="bg-surface border border-border rounded-lg px-4 py-2 text-sm" @change="load">
          <option value="month">По месяцам</option>
          <option value="quarter">По кварталам</option>
          <option value="year">По годам</option>
        </select>
      </div>
    </div>
    <div v-if="!projectId" class="text-muted py-16 text-center">Выберите проект</div>
    <div v-else-if="loading" class="text-muted py-16 text-center">Загрузка...</div>
    <template v-else-if="data">
      <div class="grid lg:grid-cols-2 gap-6 mb-8">
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">Рентабельность по периодам</h3>
          <div class="h-64">
            <Bar v-if="chartData.labels && chartData.labels.length" :data="chartData" :options="chartOptions" />
            <p v-else class="text-muted text-sm">Нет данных</p>
          </div>
        </div>
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">По проектам</h3>
          <ul class="space-y-2 max-h-64 overflow-y-auto">
            <li v-for="(r, i) in data.by_project" :key="i" class="flex justify-between text-sm">
              <span class="text-gray-300 truncate mr-2" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ r.name }}</span>
              <span class="text-accent font-mono">{{ formatPct(r.profitability_pct) }}</span>
            </li>
          </ul>
        </div>
      </div>
      <div class="grid md:grid-cols-3 gap-6">
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">По клиентам</h3>
          <ul class="space-y-2">
            <li v-for="(r, i) in data.by_client.slice(0, 10)" :key="i" class="flex justify-between text-sm">
              <span class="text-gray-300 truncate" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ r.name }}</span>
              <span class="text-accent font-mono ml-2">{{ formatMoney(r.revenue) }}</span>
            </li>
          </ul>
        </div>
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">По специалистам</h3>
          <ul class="space-y-2">
            <li v-for="(r, i) in data.by_specialist.slice(0, 10)" :key="i" class="flex justify-between text-sm">
              <span class="text-gray-300 truncate" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ r.name }}</span>
              <span class="text-accent font-mono ml-2">{{ formatMoney(r.revenue) }}</span>
            </li>
          </ul>
        </div>
        <div class="bg-surface border border-border rounded-xl p-6">
          <h3 class="text-sm font-medium text-muted mb-4">По подразделениям</h3>
          <ul class="space-y-2">
            <li v-for="(r, i) in data.by_department.slice(0, 10)" :key="i" class="flex justify-between text-sm">
              <span class="text-gray-300 truncate" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ r.name }}</span>
              <span class="text-accent font-mono ml-2">{{ formatMoney(r.revenue) }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js'
import { projects as projectsApi, analytics as analyticsApi } from '../api/client'
import { usePrivacyStore } from '../stores/privacy'
import { useAppConfigStore } from '../stores/appConfig'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const privacy = usePrivacyStore()
const appConfig = useAppConfigStore()
const projects = ref([])
const projectId = ref(null)
const groupBy = ref('month')
const loading = ref(false)
const data = ref(null)

const chartData = computed(() => ({
  labels: (data.value?.by_period || []).map((p) => p.period),
  datasets: [
    { label: 'Рентабельность %', data: (data.value?.by_period || []).map((p) => p.profitability_pct ?? 0), backgroundColor: 'rgba(34, 197, 94, 0.6)' },
  ],
}))
const chartOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }

function formatMoney(v) {
  if (v == null) return '—'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(v)) + ' ₽'
}
function formatPct(v) {
  if (v == null) return '—'
  return `${Number(v).toFixed(1)}%`
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
    data.value = await analyticsApi.get(projectId.value, { group_by: groupBy.value })
  } catch (e) {
    data.value = { by_period: [], by_project: [], by_client: [], by_specialist: [], by_department: [] }
  } finally {
    loading.value = false
  }
}
watch(projectId, load)
watch(groupBy, load)

onMounted(async () => {
  await appConfig.fetch()
  await loadProjects()
})
</script>

<template>
  <div class="animate-fade-in">
    <div class="flex items-center justify-between mb-8">
      <h1 class="font-display text-2xl font-semibold text-gray-100">Прогноз рентабельности (ИИ)</h1>
      <div class="flex items-center gap-3 flex-wrap">
        <select
          v-if="!appConfig.staticProjectEnabled"
          v-model="projectId"
          class="bg-surface border border-border rounded-lg px-4 py-2 text-sm"
          @change="load"
        >
          <option :value="null">Проект</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ projectLabel(p) }}</option>
        </select>
        <select v-model="modelType" class="bg-surface border border-border rounded-lg px-4 py-2 text-sm">
          <option value="auto">Авто (лучшая по WAPE на ретро)</option>
          <option value="ensemble">Ансамбль (ARIMA + CatBoost, веса по ретро)</option>
          <option value="arima">ARIMA</option>
          <option value="sarimax">SARIMAX (m=12)</option>
          <option value="catboost">CatBoost</option>
          <option value="lightgbm">LightGBM</option>
          <option value="prophet">Prophet</option>
          <option value="rnn">GRU (PyTorch)</option>
        </select>
        <input v-model.number="horizon" type="number" min="1" max="12" class="w-20 bg-surface border border-border rounded-lg px-3 py-2 text-sm" />
        <span class="text-muted text-sm">мес.</span>
        <button
          class="px-4 py-2 bg-accent text-void rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          :disabled="!projectId || running"
          @click="runForecast"
        >
          {{ running ? 'Расчёт...' : 'Построить прогноз' }}
        </button>
      </div>
    </div>
    <div v-if="!projectId" class="text-muted py-16 text-center">Выберите проект</div>
    <div v-else-if="running" class="text-muted py-16 text-center">Обучение модели и построение прогноза...</div>
    <template v-else-if="result">
      <p v-if="result.note" class="text-muted text-sm mb-4">{{ result.note }}</p>
      <div v-if="result.metrics && Object.keys(result.metrics).length" class="bg-surface border border-border rounded-xl p-4 mb-6 text-xs font-mono text-muted overflow-x-auto max-h-64 overflow-y-auto">
        <div class="text-muted text-sm font-sans mb-2">Метрики валидации / бизнес (JSON)</div>
        <pre class="whitespace-pre-wrap break-all">{{ metricsJson }}</pre>
      </div>
      <div class="bg-surface border border-border rounded-xl p-6 mb-6">
        <h3 class="text-sm font-medium text-muted mb-4">Прогноз рентабельности (%) — модель {{ result.model }}</h3>
        <div class="h-72">
          <Line v-if="chartData.labels && chartData.labels.length" :data="chartData" :options="chartOptions" />
          <p v-else class="text-muted text-sm">Нет точек прогноза</p>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-muted border-b border-border">
              <th class="pb-3 pr-4">Период</th>
              <th class="pb-3 pr-4">Рентабельность %</th>
              <th v-if="result.model === 'ensemble'" class="pb-3">ARIMA / CatBoost</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in result.predictions" :key="i" class="border-b border-border/50">
              <td class="py-3 pr-4 font-mono">{{ p.period }}</td>
              <td class="py-3 pr-4 text-accent">{{ (p.profitability ?? p.profitability_arima ?? p.profitability_catboost)?.toFixed(1) }}%</td>
              <td v-if="result.model === 'ensemble'" class="py-3 text-muted">
                {{ p.profitability_arima?.toFixed(1) }}% / {{ p.profitability_catboost?.toFixed(1) }}%
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <p v-else class="text-muted text-sm">
      Выберите проект, тип модели и горизонт прогноза. Для обучения нужна история помесячных метрик (не менее 12 месяцев).
    </p>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js'
import { projects as projectsApi, forecastApi } from '../api/client'
import { usePrivacyStore } from '../stores/privacy'
import { useAppConfigStore } from '../stores/appConfig'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const privacy = usePrivacyStore()
const appConfig = useAppConfigStore()
const projects = ref([])
const projectId = ref(null)
const modelType = ref('auto')
const horizon = ref(6)
const running = ref(false)
const result = ref(null)

const chartData = computed(() => {
  if (!result.value?.predictions?.length) return { labels: [], datasets: [] }
  const preds = result.value.predictions
  return {
    labels: preds.map((p) => p.period),
    datasets: [
      { label: 'Прогноз', data: preds.map((p) => p.profitability ?? p.profitability_arima ?? p.profitability_catboost), borderColor: '#22c55e', tension: 0.3, fill: false },
    ],
  }
})
const chartOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }

const metricsJson = computed(() => {
  if (!result.value?.metrics) return ''
  try {
    return JSON.stringify(result.value.metrics, null, 2)
  } catch {
    return String(result.value.metrics)
  }
})

function projectLabel(p) {
  if (!p) return ''
  return privacy.blurSensitive ? `Проект №${p.id}` : p.name
}

async function loadProjects() {
  projects.value = await projectsApi.list()
  if (projects.value.length && !projectId.value) projectId.value = projects.value[0].id
}
async function runForecast() {
  if (!projectId.value) return
  running.value = true
  result.value = null
  try {
    result.value = await forecastApi.run(projectId.value, { horizon_months: horizon.value, model_type: modelType.value })
  } catch (e) {
    result.value = null
    console.error(e)
  } finally {
    running.value = false
  }
}
onMounted(async () => {
  await appConfig.fetch()
  await loadProjects()
})
</script>

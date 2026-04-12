<template>
  <div class="animate-fade-in">
    <div class="flex items-center justify-between mb-8">
      <h1 class="font-display text-2xl font-semibold text-gray-100">
        {{ appConfig.staticProjectEnabled ? 'Синхронизация данных' : 'Проекты' }}
      </h1>
      <button
        v-if="!appConfig.staticProjectEnabled"
        class="px-4 py-2 bg-accent text-void rounded-lg text-sm font-medium hover:opacity-90"
        @click="openNew()"
      >
        Добавить проект
      </button>
    </div>

    <!-- Режим фиксированной таблицы (настройки на сервере) -->
    <template v-if="appConfig.staticProjectEnabled">
      <div v-if="!loaded" class="text-muted text-center py-12">Загрузка...</div>
      <div v-else class="bg-surface border border-border rounded-xl p-6 max-w-2xl">
        <p class="text-sm text-muted mb-4">
          Используется одна Google Таблица; ссылка и названия листов заданы на сервере. Нажмите «Синхронизировать», чтобы подтянуть данные.
        </p>
        <ul class="text-sm text-gray-300 space-y-2 mb-6 font-mono text-xs">
          <li><span class="text-muted">Лист актов (доходы):</span> Акты</li>
          <li><span class="text-muted">Лист затрат:</span> Затраты</li>
          <li><span class="text-muted">Лист специалистов:</span> TL / Специалисты</li>
        </ul>
        <div v-if="project" class="flex items-center gap-4 flex-wrap">
          <button
            class="px-4 py-2 bg-accent text-void rounded-lg text-sm font-medium hover:opacity-90"
            :disabled="syncing"
            @click="syncProject(project.id)"
          >
            {{ syncing ? 'Синхронизация...' : 'Синхронизировать' }}
          </button>
          <span v-if="project.integration?.last_sync_at" class="text-xs text-muted">
            Последняя синхронизация: {{ formatDate(project.integration.last_sync_at) }}
          </span>
        </div>
        <p v-else class="text-muted text-sm">Проект не найден. Выполните вход заново.</p>
      </div>
    </template>

    <!-- Режим с несколькими проектами -->
    <template v-else>
      <ul class="space-y-4">
        <li
          v-for="p in projects"
          :key="p.id"
          class="bg-surface border border-border rounded-xl p-5 flex items-center justify-between animate-slide-up"
        >
          <div>
            <p class="font-medium text-gray-100" :class="{ 'privacy-sensitive': privacy.blurSensitive }">{{ p.name }}</p>
            <p v-if="p.integration" class="text-xs text-muted mt-1">
              <span :class="{ 'privacy-sensitive': privacy.blurSensitive }">Таблица: {{ p.integration.spreadsheet_id }}</span>
              · Последняя синхронизация:
              {{ p.integration.last_sync_at ? formatDate(p.integration.last_sync_at) : 'никогда' }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-border transition-colors"
              :disabled="syncing === p.id"
              @click="syncProject(p.id)"
            >
              {{ syncing === p.id ? 'Синхронизация...' : 'Синхронизировать' }}
            </button>
            <button class="px-3 py-1.5 text-sm text-muted hover:text-gray-200" @click="openEdit(p)">Изменить</button>
            <button class="px-3 py-1.5 text-sm text-danger hover:opacity-80" @click="remove(p.id)">Удалить</button>
          </div>
        </li>
        <li v-if="projects.length === 0" class="text-muted text-center py-12">Нет проектов. Добавьте проект и укажите ссылку на Google Таблицу.</li>
      </ul>
      <div v-if="showForm" class="fixed inset-0 bg-black/60 flex items-center justify-center z-20 p-4" @click.self="showForm = false">
        <div class="bg-surface border border-border rounded-xl p-6 w-full max-w-md animate-slide-up">
          <h3 class="font-display text-lg font-semibold text-gray-100 mb-4">{{ editProject ? 'Редактировать проект' : 'Новый проект' }}</h3>
          <form @submit.prevent="submit">
            <div class="space-y-4">
              <div>
                <label class="block text-sm text-muted mb-1">Название</label>
                <input v-model="form.name" type="text" required class="w-full bg-void border border-border rounded-lg px-4 py-2 text-gray-100" placeholder="Название проекта" />
              </div>
              <div>
                <label class="block text-sm text-muted mb-1">Ссылка на Google Таблицу</label>
                <input v-model="form.spreadsheet_url" type="url" class="w-full bg-void border border-border rounded-lg px-4 py-2 text-gray-100" placeholder="https://docs.google.com/spreadsheets/d/..." />
              </div>
              <p class="text-xs text-muted mt-2">Названия листов (как во вкладках таблицы):</p>
              <div>
                <label class="block text-sm text-muted mb-1">Лист актов (доходы)</label>
                <input v-model="form.sheet_acts" type="text" class="w-full bg-void border border-border rounded-lg px-4 py-2 text-gray-100" placeholder="Акты" />
              </div>
              <div>
                <label class="block text-sm text-muted mb-1">Лист затрат</label>
                <input v-model="form.sheet_costs" type="text" class="w-full bg-void border border-border rounded-lg px-4 py-2 text-gray-100" placeholder="Затраты" />
              </div>
              <div>
                <label class="block text-sm text-muted mb-1">Лист специалистов (выручка по месяцам — строки 66, 139, 160)</label>
                <input v-model="form.sheet_specialists" type="text" class="w-full bg-void border border-border rounded-lg px-4 py-2 text-gray-100" placeholder="TL или TL / Специалисты" />
              </div>
            </div>
            <div class="flex justify-end gap-2 mt-6">
              <button type="button" class="px-4 py-2 text-muted hover:text-gray-200" @click="showForm = false">Отмена</button>
              <button type="submit" class="px-4 py-2 bg-accent text-void rounded-lg font-medium">Сохранить</button>
            </div>
          </form>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { projects as projectsApi, sync as syncApi } from '../api/client'
import { usePrivacyStore } from '../stores/privacy'
import { useAppConfigStore } from '../stores/appConfig'

const privacy = usePrivacyStore()
const appConfig = useAppConfigStore()

const projects = ref([])
const project = computed(() => projects.value[0] ?? null)
const loaded = ref(false)
const showForm = ref(false)
const editProject = ref(null)
const syncing = ref(null)
const form = ref({
  name: '',
  spreadsheet_url: '',
  sheet_acts: 'Акты',
  sheet_costs: 'Затраты',
  sheet_specialists: 'TL',
})

function formatDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleString('ru-RU')
}

async function load() {
  projects.value = await projectsApi.list()
}

async function init() {
  await appConfig.fetch()
  await load()
  loaded.value = true
}

function openNew() {
  editProject.value = null
  form.value = { name: '', spreadsheet_url: '', sheet_acts: 'Акты', sheet_costs: 'Затраты', sheet_specialists: 'TL' }
  showForm.value = true
}
function openEdit(p) {
  editProject.value = p
  const i = p.integration
  form.value = {
    name: p.name,
    spreadsheet_url: i ? `https://docs.google.com/spreadsheets/d/${i.spreadsheet_id}/edit` : '',
    sheet_acts: i?.sheet_acts ?? 'Акты',
    sheet_costs: i?.sheet_costs ?? 'Затраты',
    sheet_specialists: i?.sheet_specialists ?? 'TL',
  }
  showForm.value = true
}
async function submit() {
  const body = {
    name: form.value.name,
    integration: form.value.spreadsheet_url
      ? {
          spreadsheet_url: form.value.spreadsheet_url,
          sheet_acts: form.value.sheet_acts || 'Акты',
          sheet_costs: form.value.sheet_costs || 'Затраты',
          sheet_specialists: form.value.sheet_specialists || 'TL',
        }
      : null,
  }
  if (editProject.value) {
    await projectsApi.update(editProject.value.id, body)
  } else {
    await projectsApi.create(body)
  }
  showForm.value = false
  editProject.value = null
  load()
}
async function syncProject(id) {
  syncing.value = id
  try {
    await syncApi.run(id)
  } catch (e) {
    // ignore
  } finally {
    syncing.value = null
    load()
  }
}
async function remove(id) {
  if (!confirm('Удалить проект?')) return
  await projectsApi.delete(id)
  load()
}

onMounted(init)
</script>

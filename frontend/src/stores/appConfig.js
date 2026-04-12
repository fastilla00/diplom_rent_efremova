import { defineStore } from 'pinia'
import client from '../api/client'

export const useAppConfigStore = defineStore('appConfig', {
  state: () => ({
    staticProjectEnabled: false,
    loaded: false,
  }),
  actions: {
    async fetch() {
      if (this.loaded) return
      try {
        const c = await client.get('/config').then((r) => r.data)
        this.staticProjectEnabled = !!c.static_project_enabled
      } catch {
        this.staticProjectEnabled = false
      }
      this.loaded = true
    },
  },
})

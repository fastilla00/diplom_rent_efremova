import { defineStore } from 'pinia'
import { auth as authApi } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token'),
    user: (() => {
      try {
        return JSON.parse(localStorage.getItem('user') || 'null')
      } catch {
        return null
      }
    })(),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    userName: (s) => s.user?.name || s.user?.email || 'Пользователь',
  },
  actions: {
    setAuth(token, user) {
      this.token = token
      this.user = user
      if (token) localStorage.setItem('token', token)
      else localStorage.removeItem('token')
      if (user) localStorage.setItem('user', JSON.stringify(user))
      else localStorage.removeItem('user')
    },
    async fetchMe() {
      const user = await authApi.me()
      this.user = user
      localStorage.setItem('user', JSON.stringify(user))
      return user
    },
    logout() {
      this.setAuth(null, null)
    },
  },
})

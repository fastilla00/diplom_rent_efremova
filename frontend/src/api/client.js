import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default client

export const auth = {
  getGoogleUrl: () => client.get('/auth/google').then((r) => r.data),
  callback: (code, state) => client.post('/auth/callback', { code, state }).then((r) => r.data),
  me: () => client.get('/auth/me').then((r) => r.data),
}

export const projects = {
  list: () => client.get('/projects').then((r) => r.data),
  get: (id) => client.get(`/projects/${id}`).then((r) => r.data),
  create: (body) => client.post('/projects', body).then((r) => r.data),
  update: (id, body) => client.patch(`/projects/${id}`, body).then((r) => r.data),
  delete: (id) => client.delete(`/projects/${id}`),
}

export const sync = {
  run: (projectId) => client.post(`/sync/${projectId}`).then((r) => r.data),
}

export const dashboard = {
  get: (projectId, params) => client.get(`/dashboard/${projectId}`, { params }).then((r) => r.data),
}

export const analytics = {
  get: (projectId, params) => client.get(`/analytics/${projectId}`, { params }).then((r) => r.data),
}

export const alertsApi = {
  list: (projectId, params) => client.get(`/alerts/${projectId}`, { params }).then((r) => r.data),
  compute: (projectId, params) => client.post(`/alerts/${projectId}/compute`, null, { params }).then((r) => r.data),
}

export const forecastApi = {
  run: (projectId, body) => client.post(`/forecast/${projectId}`, body).then((r) => r.data),
}

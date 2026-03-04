import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const key = localStorage.getItem('api_key')
  if (key) {
    config.headers['X-API-Key'] = key
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('api_key')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // Send cookies with every request
})

// Token refresh state
let isRefreshing = false
let failedQueue: Array<{ resolve: () => void; reject: (err: unknown) => void }> = []

function processQueue(error: unknown) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve()
  })
  failedQueue = []
}

function redirectToLogin() {
  // Assigning location.href triggers a full navigation even when the URL is
  // unchanged — on /login that reload remounts the app, whose session probe
  // 401s again, looping forever. Only navigate when we're somewhere else.
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Only attempt refresh on 401, and only once per request
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't retry the refresh endpoint itself — would cause infinite loop
      if (originalRequest.url?.includes('/auth/refresh')) {
        redirectToLogin()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Mark as retried to prevent re-entering refresh logic on retry
        originalRequest._retry = true
        return new Promise<void>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then(() => api(originalRequest))
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        await api.post('/auth/refresh')
        processQueue(null)
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError)
        // Redirect to login — session expired
        redirectToLogin()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default api

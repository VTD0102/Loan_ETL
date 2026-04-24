import axios from 'axios'
import { mockHandlers } from '../mocks/mockHandlers'

const isMock = import.meta.env.VITE_MOCK_MODE === 'true'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Mock interceptor — short-circuits real HTTP calls when VITE_MOCK_MODE=true
if (isMock) {
  api.interceptors.request.use(async (config) => {
    const [status, data] = await mockHandlers(config)

    // Simulate axios response/error shape
    if (status >= 400) {
      const err = Object.assign(new Error(`Mock error ${status}`), {
        response: { status, data, config },
      })
      return Promise.reject(err)
    }

    // Cancel the real request and return mock response
    const controller = new AbortController()
    controller.abort()
    config.signal = controller.signal
    config.__mockResponse = { status, data }
    return config
  })

  api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.config?.__mockResponse) {
        const { status, data } = error.config.__mockResponse
        return Promise.resolve({ status, data, config: error.config, headers: {} })
      }
      // Real 401 handling (won't fire in mock mode, but keep for safety)
      if (error.response?.status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    },
  )
} else {
  // Production: handle 401 globally
  api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    },
  )
}

export { isMock }
export default api

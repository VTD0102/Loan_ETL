import { create } from 'zustand'

const stored = () => {
  try {
    const u = localStorage.getItem('user')
    return u ? JSON.parse(u) : null
  } catch { return null }
}

const useAuthStore = create((set) => ({
  token: localStorage.getItem('token') || null,
  user:  stored(),

  setAuth: (token, user) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user',  JSON.stringify(user))
    set({ token, user })
  },

  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    set({ token: null, user: null })
  },

  setUser: (user) => {
    localStorage.setItem('user', JSON.stringify(user))
    set({ user })
  },

  isAuthenticated: () => !!localStorage.getItem('token'),
}))

export default useAuthStore

/**
 * Authentication state management using Zustand.
 */
import { create } from 'zustand'
import { api } from '../services/api'

interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: 'admin' | 'manager' | 'cashier'
  is_active: boolean
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  loadUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('auth_token'),
  isAuthenticated: !!localStorage.getItem('auth_token'),
  isLoading: false,

  login: async (username: string, password: string) => {
    set({ isLoading: true })
    try {
      const data = await api.login(username, password)
      const token = data.access_token

      localStorage.setItem('auth_token', token)

      // Fetch user data
      const user = await api.getCurrentUser()
      localStorage.setItem('user', JSON.stringify(user))

      set({
        user,
        token,
        isAuthenticated: true,
        isLoading: false,
      })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  logout: () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user')
    set({
      user: null,
      token: null,
      isAuthenticated: false,
    })
  },

  loadUser: async () => {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      set({ isAuthenticated: false })
      return
    }

    try {
      const user = await api.getCurrentUser()
      set({
        user,
        isAuthenticated: true,
      })
    } catch (error) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user')
      set({
        user: null,
        token: null,
        isAuthenticated: false,
      })
    }
  },
}))

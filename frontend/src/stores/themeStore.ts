/**
 * Theme state management for light/dark mode.
 */
import { create } from 'zustand'

interface ThemeState {
  isDark: boolean
  toggleTheme: () => void
  setTheme: (isDark: boolean) => void
}

export const useThemeStore = create<ThemeState>((set) => {
  // Initialize theme from localStorage or system preference
  const savedTheme = localStorage.getItem('theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const initialDark = savedTheme ? savedTheme === 'dark' : prefersDark

  // Apply initial theme
  if (initialDark) {
    document.documentElement.classList.add('dark')
  }

  return {
    isDark: initialDark,

    toggleTheme: () => {
      set((state) => {
        const newIsDark = !state.isDark
        if (newIsDark) {
          document.documentElement.classList.add('dark')
          localStorage.setItem('theme', 'dark')
        } else {
          document.documentElement.classList.remove('dark')
          localStorage.setItem('theme', 'light')
        }
        return { isDark: newIsDark }
      })
    },

    setTheme: (isDark) => {
      if (isDark) {
        document.documentElement.classList.add('dark')
        localStorage.setItem('theme', 'dark')
      } else {
        document.documentElement.classList.remove('dark')
        localStorage.setItem('theme', 'light')
      }
      set({ isDark })
    },
  }
})

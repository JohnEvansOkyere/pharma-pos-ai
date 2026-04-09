import { beforeEach, describe, expect, it, vi } from 'vitest'

const loginMock = vi.fn()
const getCurrentUserMock = vi.fn()

vi.mock('../services/api', () => ({
  api: {
    login: (...args: unknown[]) => loginMock(...args),
    getCurrentUser: (...args: unknown[]) => getCurrentUserMock(...args),
  },
}))

describe('authStore', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.resetModules()
  })

  it('trims username, stores auth state, and persists user data on login', async () => {
    loginMock.mockResolvedValue({ access_token: 'token-123' })
    getCurrentUserMock.mockResolvedValue({
      id: 1,
      username: 'manager',
      email: 'manager@example.com',
      full_name: 'Manager User',
      role: 'manager',
      is_active: true,
    })

    const { useAuthStore } = await import('./authStore')
    const user = await useAuthStore.getState().login('  manager  ', 'secret')

    expect(loginMock).toHaveBeenCalledWith('manager', 'secret')
    expect(localStorage.getItem('auth_token')).toBe('token-123')
    expect(JSON.parse(localStorage.getItem('user') || '{}').username).toBe('manager')
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(user.role).toBe('manager')
  })

  it('clears local auth state when loadUser fails with an invalid token', async () => {
    localStorage.setItem('auth_token', 'stale-token')
    localStorage.setItem('user', JSON.stringify({ username: 'stale' }))
    getCurrentUserMock.mockRejectedValue(new Error('invalid token'))

    const { useAuthStore } = await import('./authStore')
    await useAuthStore.getState().loadUser()

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().user).toBeNull()
  })
})

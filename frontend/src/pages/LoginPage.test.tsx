import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const navigateMock = vi.fn()
const successMock = vi.fn()
const errorMock = vi.fn()
const loginMock = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

vi.mock('react-hot-toast', () => ({
  default: {
    success: (...args: unknown[]) => successMock(...args),
    error: (...args: unknown[]) => errorMock(...args),
  },
}))

vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    login: (...args: unknown[]) => loginMock(...args),
  }),
}))

import LoginPage from './LoginPage'

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('navigates admins to the dashboard after successful login', async () => {
    loginMock.mockResolvedValue({ role: 'admin' })
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    await user.type(screen.getByPlaceholderText(/enter your username/i), 'admin')
    await user.type(screen.getByPlaceholderText(/enter your password/i), 'secret')
    await user.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(successMock).toHaveBeenCalledWith('Login successful!')
      expect(navigateMock).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('shows backend error details on failed login', async () => {
    loginMock.mockRejectedValue({ response: { data: { detail: 'Incorrect username or password' } } })
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    await user.type(screen.getByPlaceholderText(/enter your username/i), 'admin')
    await user.type(screen.getByPlaceholderText(/enter your password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(errorMock).toHaveBeenCalledWith('Incorrect username or password')
    })
    expect(navigateMock).not.toHaveBeenCalled()
  })
})

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getUsersMock = vi.fn()
const getBackupStatusMock = vi.fn()
const getSystemDiagnosticsMock = vi.fn()
const triggerBackupNowMock = vi.fn()
const successMock = vi.fn()
const errorMock = vi.fn()

vi.mock('../services/api', () => ({
  api: {
    getUsers: (...args: unknown[]) => getUsersMock(...args),
    getBackupStatus: (...args: unknown[]) => getBackupStatusMock(...args),
    getSystemDiagnostics: (...args: unknown[]) => getSystemDiagnosticsMock(...args),
    triggerBackupNow: (...args: unknown[]) => triggerBackupNowMock(...args),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    deleteUser: vi.fn(),
  },
}))

vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    user: {
      id: 1,
      username: 'manager',
      email: 'manager@example.com',
      full_name: 'Manager User',
      role: 'manager',
      is_active: true,
    },
  }),
}))

vi.mock('react-hot-toast', () => ({
  default: {
    success: (...args: unknown[]) => successMock(...args),
    error: (...args: unknown[]) => errorMock(...args),
  },
}))

import SettingsPage from './SettingsPage'

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getUsersMock.mockResolvedValue([])
    getBackupStatusMock.mockResolvedValue({
      platform: 'Linux',
      backup_dir: '/var/backups/pharma',
      latest_backup_path: '/var/backups/pharma/latest.dump',
      latest_backup_exists: true,
      latest_backup_time: '2026-04-09T18:00:00',
      latest_backup_size_bytes: 1048576,
      latest_backup_age_hours: 1.2,
      backup_is_recent: true,
      retention_days: 30,
      trigger_available: true,
      schedule_helper_available: true,
    })
    getSystemDiagnosticsMock.mockResolvedValue({
      platform: 'Linux',
      app_version: '1.0.0',
      environment: 'production',
      database_backend: 'postgresql',
      database_connected: true,
      scheduler_enabled: true,
      scheduler_running: true,
      scheduler_job_count: 2,
      backup_dir: '/var/backups/pharma',
      latest_backup_exists: true,
      latest_backup_time: '2026-04-09T18:00:00',
      backup_is_recent: true,
      frontend_dist_available: true,
      windows_backup_task_helper_available: false,
      linux_backup_cron_helper_available: true,
    })
  })

  it('loads backup status and diagnostics for manager users', async () => {
    render(<SettingsPage />)

    expect(await screen.findByText(/backup status/i)).toBeInTheDocument()
    expect(await screen.findByText(/recent and healthy/i)).toBeInTheDocument()
    expect(await screen.findByText('/var/backups/pharma')).toBeInTheDocument()
    expect(await screen.findByText(/connected/i)).toBeInTheDocument()
    expect(getBackupStatusMock).toHaveBeenCalled()
    expect(getSystemDiagnosticsMock).toHaveBeenCalled()
  })

  it('triggers a manual backup and shows success feedback', async () => {
    triggerBackupNowMock.mockResolvedValue({
      backup: {
        platform: 'Linux',
        backup_dir: '/var/backups/pharma',
        latest_backup_path: '/var/backups/pharma/manual.dump',
        latest_backup_exists: true,
        latest_backup_time: '2026-04-09T19:00:00',
        latest_backup_size_bytes: 2048,
        latest_backup_age_hours: 0.0,
        backup_is_recent: true,
        retention_days: 30,
        trigger_available: true,
        schedule_helper_available: true,
      },
    })
    const user = userEvent.setup()

    render(<SettingsPage />)

    await screen.findByText(/backup status/i)
    await user.click(screen.getByRole('button', { name: /back up now/i }))

    await waitFor(() => {
      expect(triggerBackupNowMock).toHaveBeenCalled()
      expect(successMock).toHaveBeenCalledWith('Backup completed successfully')
    })
  })
})

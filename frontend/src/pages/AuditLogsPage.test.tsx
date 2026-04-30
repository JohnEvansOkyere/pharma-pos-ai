import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getAuditLogs: vi.fn(),
  exportAuditLogsCsv: vi.fn(),
}))

vi.mock('../services/api', () => ({
  api: apiMocks,
}))

vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    user: {
      id: 7,
      username: 'admin',
      email: 'admin@example.com',
      full_name: 'Admin User',
      role: 'admin',
      organization_id: 22,
      branch_id: null,
      is_active: true,
    },
  }),
}))

import AuditLogsPage from './AuditLogsPage'

describe('AuditLogsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getAuditLogs.mockResolvedValue({
      total: 1,
      limit: 100,
      offset: 0,
      items: [
        {
          id: 101,
          organization_id: 22,
          branch_id: 3,
          source_device_id: null,
          user_id: 7,
          action: 'update_ai_external_provider_policy',
          entity_type: 'ai_external_provider_setting',
          entity_id: 9,
          description: 'Updated tenant external AI provider policy',
          extra_data: { external_ai_enabled: true, preferred_provider: 'groq' },
          ip_address: null,
          created_at: '2026-05-03T18:20:00Z',
        },
      ],
    })
    apiMocks.exportAuditLogsCsv.mockResolvedValue(new Blob(['id,action\n101,update_ai_external_provider_policy']))
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:audit-logs'),
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  it('loads tenant scoped audit logs for the current admin organization', async () => {
    render(<AuditLogsPage />)

    expect(await screen.findByText(/audit logs/i)).toBeInTheDocument()
    expect(await screen.findByText(/update ai external provider policy/i)).toBeInTheDocument()
    expect(await screen.findByText(/Org 22 · Branch 3/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(apiMocks.getAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22, limit: 100, offset: 0 })
      )
    })
  })

  it('applies filters and exports the current audit scope', async () => {
    const user = userEvent.setup()
    render(<AuditLogsPage />)

    await screen.findByText(/update ai external provider policy/i)
    await user.type(screen.getByLabelText(/action/i), 'review_ai_weekly_report')
    await user.click(screen.getByRole('button', { name: /apply filters/i }))

    await waitFor(() => {
      expect(apiMocks.getAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({
          organization_id: 22,
          action: 'review_ai_weekly_report',
          limit: 100,
          offset: 0,
        })
      )
    })

    await user.click(screen.getByRole('button', { name: /export csv/i }))

    await waitFor(() => {
      expect(apiMocks.exportAuditLogsCsv).toHaveBeenCalledWith(
        expect.objectContaining({
          organization_id: 22,
          action: 'review_ai_weekly_report',
          limit: 5000,
        })
      )
    })
  })
})

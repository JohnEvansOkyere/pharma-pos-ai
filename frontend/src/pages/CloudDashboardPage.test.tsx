import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getCloudSalesSummary: vi.fn(),
  getCloudBranchSales: vi.fn(),
  getCloudInventoryMovementSummary: vi.fn(),
  getCloudSyncHealth: vi.fn(),
}))

vi.mock('../services/api', () => ({
  api: apiMocks,
}))

vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    user: {
      id: 7,
      username: 'owner',
      email: 'owner@example.com',
      full_name: 'Owner User',
      role: 'manager',
      organization_id: 22,
      branch_id: null,
      is_active: true,
    },
  }),
}))

vi.mock('recharts', () => {
  const Mock = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  return {
    ResponsiveContainer: Mock,
    BarChart: Mock,
    Bar: Mock,
    CartesianGrid: Mock,
    Tooltip: Mock,
    XAxis: Mock,
    YAxis: Mock,
  }
})

import CloudDashboardPage from './CloudDashboardPage'

describe('CloudDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getCloudSalesSummary.mockResolvedValue({
      organization_id: 22,
      branch_id: null,
      sales_count: 12,
      total_revenue: 580.5,
      total_items: 31,
    })
    apiMocks.getCloudBranchSales.mockResolvedValue([
      { branch_id: 1, sales_count: 7, total_revenue: 300, total_items: 18 },
      { branch_id: 2, sales_count: 5, total_revenue: 280.5, total_items: 13 },
    ])
    apiMocks.getCloudInventoryMovementSummary.mockResolvedValue({
      organization_id: 22,
      branch_id: null,
      movement_count: 4,
      total_positive_quantity: 20,
      total_negative_quantity: -8,
      net_quantity_delta: 12,
    })
    apiMocks.getCloudSyncHealth.mockResolvedValue({
      organization_id: 22,
      branch_id: null,
      ingested_event_count: 20,
      projected_event_count: 18,
      projection_failed_count: 1,
      duplicate_delivery_count: 2,
      last_received_at: '2026-04-29T08:00:00Z',
      last_projected_at: '2026-04-29T08:05:00Z',
    })
  })

  it('loads cloud reporting sections using the current user organization', async () => {
    render(<CloudDashboardPage />)

    expect(await screen.findByText(/cloud dashboard/i)).toBeInTheDocument()
    expect(await screen.findByText('GH₵ 580.50')).toBeInTheDocument()
    expect(await screen.findByText('31')).toBeInTheDocument()
    expect(await screen.findByText('12 sales')).toBeInTheDocument()
    expect(await screen.findByText(/ingested events/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(apiMocks.getCloudSalesSummary).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22 })
      )
      expect(apiMocks.getCloudBranchSales).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22 })
      )
      expect(apiMocks.getCloudInventoryMovementSummary).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22 })
      )
      expect(apiMocks.getCloudSyncHealth).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22 })
      )
    })
  })
})

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getCloudSalesSummary: vi.fn(),
  getCloudBranchSales: vi.fn(),
  getCloudInventoryMovementSummary: vi.fn(),
  getCloudSyncHealth: vi.fn(),
  getCloudStockRiskSummary: vi.fn(),
  getCloudLowStock: vi.fn(),
  getCloudExpiryRisk: vi.fn(),
  chatWithAIManager: vi.fn(),
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
    apiMocks.getCloudStockRiskSummary.mockResolvedValue({
      organization_id: 22,
      branch_id: null,
      low_stock_count: 1,
      out_of_stock_count: 1,
      near_expiry_batch_count: 2,
      expired_batch_count: 1,
      total_quantity_on_hand: 44,
      value_at_risk: 125.5,
      expiry_warning_days: 90,
    })
    apiMocks.getCloudLowStock.mockResolvedValue([
      {
        branch_id: 1,
        product_id: 8,
        product_name: 'Low Stock Tablets',
        sku: 'LOW-8',
        total_stock: 2,
        low_stock_threshold: 5,
        units_needed: 8,
        status: 'low_stock',
      },
    ])
    apiMocks.getCloudExpiryRisk.mockResolvedValue([
      {
        branch_id: 1,
        product_id: 9,
        product_name: 'Expiry Risk Syrup',
        sku: 'EXP-9',
        batch_id: 20,
        batch_number: 'EXP-20',
        quantity: 5,
        expiry_date: '2026-05-10',
        days_until_expiry: 11,
        value_at_risk: 125.5,
        status: 'near_expiry',
      },
    ])
    apiMocks.chatWithAIManager.mockResolvedValue({
      answer: 'Branch 2 is performing best from approved cloud report data.',
      data_scope: {
        organization_id: 22,
        branch_id: null,
        period_days: 30,
        sources: ['cloud_sale_facts'],
      },
      tool_results: {},
      safety_notes: ['Read-only assistant: it does not mutate stock, sales, users, or sync records.'],
      provider: 'groq',
      model: 'llama-3.3-70b-versatile',
      fallback_used: false,
      refused: false,
    })
  })

  it('loads cloud reporting sections using the current user organization', async () => {
    render(<CloudDashboardPage />)

    expect(await screen.findByText(/cloud dashboard/i)).toBeInTheDocument()
    expect(await screen.findByText('GH₵ 580.50')).toBeInTheDocument()
    expect(await screen.findByText('31')).toBeInTheDocument()
    expect(await screen.findByText('12 sales')).toBeInTheDocument()
    expect(await screen.findByText(/ingested events/i)).toBeInTheDocument()
    expect(await screen.findByText(/low stock tablets/i)).toBeInTheDocument()
    expect(await screen.findByText(/expiry risk syrup/i)).toBeInTheDocument()

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
      expect(apiMocks.getCloudStockRiskSummary).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22, expiry_warning_days: 90 })
      )
      expect(apiMocks.getCloudLowStock).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22, limit: 10 })
      )
      expect(apiMocks.getCloudExpiryRisk).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22, days: 90, limit: 10 })
      )
    })
  })

  it('sends scoped AI manager chat requests and renders provider metadata', async () => {
    const user = userEvent.setup()
    render(<CloudDashboardPage />)

    await screen.findByText(/ai manager assistant/i)
    await user.click(screen.getByRole('button', { name: /which branch is performing best/i }))

    expect(await screen.findByText(/branch 2 is performing best/i)).toBeInTheDocument()
    expect(await screen.findByText(/provider: groq/i)).toBeInTheDocument()
    expect(await screen.findByText(/fallback: no/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(apiMocks.chatWithAIManager).toHaveBeenCalledWith({
        message: 'Which branch is performing best?',
        organization_id: 22,
        period_days: 30,
      })
    })
  })
})

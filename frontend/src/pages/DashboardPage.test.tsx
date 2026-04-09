import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiMocks } = vi.hoisted(() => ({
  apiMocks: {
    getDashboardKPIs: vi.fn(),
    getSalesTrend: vi.fn(),
    getFastMovingProducts: vi.fn(),
    getSlowMovingProducts: vi.fn(),
    getRevenueAnalysis: vi.fn(),
    getFinancialKPIs: vi.fn(),
    getExpiringProducts: vi.fn(),
    getLowStockItems: vi.fn(),
    getProfitByCategory: vi.fn(),
  },
}))

vi.mock('../services/api', () => ({
  api: apiMocks,
}))

vi.mock('recharts', () => {
  const Mock = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  return {
    ResponsiveContainer: Mock,
    LineChart: Mock,
    Line: Mock,
    BarChart: Mock,
    Bar: Mock,
    XAxis: Mock,
    YAxis: Mock,
    CartesianGrid: Mock,
    Tooltip: Mock,
    Legend: Mock,
    ComposedChart: Mock,
  }
})

import DashboardPage from './DashboardPage'

const dashboardApi = {
  getDashboardKPIs: vi.fn(),
  getSalesTrend: vi.fn(),
  getFastMovingProducts: vi.fn(),
  getSlowMovingProducts: vi.fn(),
  getRevenueAnalysis: vi.fn(),
  getFinancialKPIs: vi.fn(),
  getExpiringProducts: vi.fn(),
  getLowStockItems: vi.fn(),
  getProfitByCategory: vi.fn(),
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(dashboardApi, apiMocks)
    dashboardApi.getDashboardKPIs.mockResolvedValue({
      total_sales_today: 250,
      profit_today: 70,
      inventory_value: 4000,
      items_near_expiry: 1,
      low_stock_items: 2,
      total_products: 25,
      total_sales_count: 8,
    })
    dashboardApi.getSalesTrend.mockResolvedValue([{ date: '2026-04-09', sales_count: 3, total_revenue: 120 }])
    dashboardApi.getFastMovingProducts.mockResolvedValue([{ product_id: 1, product_name: 'Amox', total_revenue: 120, total_sold: 4 }])
    dashboardApi.getSlowMovingProducts.mockResolvedValue([])
    dashboardApi.getRevenueAnalysis.mockResolvedValue({
      daily_revenue: 250,
      daily_transactions: 8,
      weekly_revenue: 1000,
      weekly_transactions: 20,
      monthly_revenue: 3000,
      monthly_transactions: 70,
      average_basket_value: 31.25,
    })
    dashboardApi.getFinancialKPIs.mockRejectedValue(new Error('financial endpoint failed'))
    dashboardApi.getExpiringProducts.mockResolvedValue([
      {
        product_id: 1,
        product_name: 'Near Expiry Syrup',
        sku: 'NE-1',
        dosage_form: 'SYRUP',
        strength: '100mg',
        batch_number: 'B1',
        batch_quantity: 4,
        expiry_date: '2026-04-20',
        days_until_expiry: 11,
        value_at_risk: 40,
      },
    ])
    dashboardApi.getLowStockItems.mockResolvedValue([
      {
        product_id: 2,
        product_name: 'Low Stock Tablets',
        sku: 'LS-1',
        dosage_form: 'TABLET',
        strength: '500mg',
        current_stock: 0,
        low_stock_threshold: 5,
        reorder_level: 10,
        units_needed: 10,
        status: 'out_of_stock',
      },
    ])
    dashboardApi.getProfitByCategory.mockResolvedValue([])
  })

  it('renders successful sections even when one dashboard request fails', async () => {
    render(<DashboardPage />)

    expect(await screen.findByText(/business dashboard/i)).toBeInTheDocument()
    expect(await screen.findByText(/critical inventory alerts/i)).toBeInTheDocument()
    expect(await screen.findByText(/low stock tablets/i)).toBeInTheDocument()
    expect(await screen.findByText(/near expiry syrup/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(dashboardApi.getFinancialKPIs).toHaveBeenCalled()
      expect(dashboardApi.getDashboardKPIs).toHaveBeenCalled()
    })
  })
})

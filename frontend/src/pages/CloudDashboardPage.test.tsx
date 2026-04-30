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
  getCloudReconciliation: vi.fn(),
  getAIWeeklyReports: vi.fn(),
  generateAIWeeklyReport: vi.fn(),
  deliverAIWeeklyReport: vi.fn(),
  getAIWeeklyReportDeliveries: vi.fn(),
  getAIWeeklyReportDeliverySetting: vi.fn(),
  updateAIWeeklyReportDeliverySetting: vi.fn(),
  chatWithAIManager: vi.fn(),
}))

const authMock = vi.hoisted(() => ({
  user: {
    id: 7,
    username: 'owner',
    email: 'owner@example.com',
    full_name: 'Owner User',
    role: 'manager',
    organization_id: 22,
    branch_id: null as number | null,
    is_active: true,
  },
}))

vi.mock('../services/api', () => ({
  api: apiMocks,
}))

vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    user: authMock.user,
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
    authMock.user = {
      id: 7,
      username: 'owner',
      email: 'owner@example.com',
      full_name: 'Owner User',
      role: 'manager',
      organization_id: 22,
      branch_id: null,
      is_active: true,
    }
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
    apiMocks.getCloudReconciliation.mockResolvedValue({
      organization_id: 22,
      branch_id: null,
      product_snapshot_count: 3,
      batch_snapshot_count: 4,
      movement_fact_count: 5,
      projection_failed_count: 1,
      issue_count: 2,
      critical_issue_count: 1,
      high_issue_count: 1,
      medium_issue_count: 0,
      issues: [
        {
          severity: 'critical',
          issue_type: 'negative_product_stock',
          branch_id: 1,
          product_id: 8,
          batch_id: null,
          product_name: 'Low Stock Tablets',
          batch_number: null,
          expected_quantity: null,
          actual_quantity: -1,
          delta: null,
          message: 'Product snapshot total stock is negative.',
        },
      ],
    })
    apiMocks.getAIWeeklyReports.mockResolvedValue([
      {
        id: 55,
        organization_id: 22,
        branch_id: null,
        generated_by_user_id: 7,
        performance_period_start: '2026-04-26T19:00:00Z',
        performance_period_end: '2026-05-03T19:00:00Z',
        action_period_start: '2026-05-04',
        action_period_end: '2026-05-10',
        title: 'Weekly Manager Report: 2026-04-26 to 2026-05-03 | Action Plan 2026-05-04 to 2026-05-10',
        executive_summary: 'Weekly summary with coming week action priorities.',
        sections: {
          coming_week_action_plan: {
            risk_counts: {
              out_of_stock_count: 1,
              low_stock_count: 1,
              expired_batch_count: 1,
              near_expiry_batch_count: 2,
              value_at_risk: 125.5,
            },
          },
          sync_and_data_quality: {
            reconciliation: {
              issue_count: 2,
              critical_issue_count: 1,
              high_issue_count: 1,
              medium_issue_count: 0,
            },
          },
        },
        safety_notes: ['Read-only assistant.'],
        provider: 'groq',
        model: 'llama-3.3-70b-versatile',
        fallback_used: false,
        generated_at: '2026-05-03T19:00:00Z',
      },
    ])
    apiMocks.generateAIWeeklyReport.mockResolvedValue({
      id: 55,
      organization_id: 22,
      branch_id: null,
      generated_by_user_id: 7,
      performance_period_start: '2026-04-26T19:00:00Z',
      performance_period_end: '2026-05-03T19:00:00Z',
      action_period_start: '2026-05-04',
      action_period_end: '2026-05-10',
      title: 'Weekly Manager Report: 2026-04-26 to 2026-05-03 | Action Plan 2026-05-04 to 2026-05-10',
      executive_summary: 'Weekly summary with coming week action priorities.',
      sections: {
        coming_week_action_plan: { risk_counts: { out_of_stock_count: 1, low_stock_count: 1 } },
        sync_and_data_quality: { reconciliation: { issue_count: 2 } },
      },
      safety_notes: ['Read-only assistant.'],
      provider: 'groq',
      model: null,
      fallback_used: false,
      generated_at: '2026-05-03T19:00:00Z',
    })
    apiMocks.deliverAIWeeklyReport.mockResolvedValue([
      {
        id: 101,
        report_id: 55,
        organization_id: 22,
        branch_id: null,
        channel: 'email',
        recipient: 'owner@example.com',
        status: 'sent',
        attempt_count: 1,
        error_message: null,
        sent_at: '2026-05-03T19:05:00Z',
        created_at: '2026-05-03T19:05:00Z',
      },
    ])
    apiMocks.getAIWeeklyReportDeliveries.mockResolvedValue([
      {
        id: 88,
        report_id: 55,
        organization_id: 22,
        branch_id: null,
        channel: 'telegram',
        recipient: '12345',
        status: 'skipped',
        attempt_count: 1,
        error_message: 'Telegram weekly report delivery is disabled for this tenant scope.',
        sent_at: null,
        created_at: '2026-05-03T19:01:00Z',
      },
    ])
    apiMocks.getAIWeeklyReportDeliverySetting.mockResolvedValue({
      id: 10,
      organization_id: 22,
      branch_id: null,
      report_scope_key: 'organization',
      email_enabled: true,
      email_recipients: ['owner@example.com'],
      telegram_enabled: false,
      telegram_chat_ids: [],
      is_active: true,
      created_at: '2026-05-03T18:00:00Z',
      updated_at: '2026-05-03T18:00:00Z',
    })
    apiMocks.updateAIWeeklyReportDeliverySetting.mockResolvedValue({
      id: 10,
      organization_id: 22,
      branch_id: null,
      report_scope_key: 'organization',
      email_enabled: true,
      email_recipients: ['owner@example.com', 'ops@example.com'],
      telegram_enabled: true,
      telegram_chat_ids: ['12345'],
      is_active: true,
      created_at: '2026-05-03T18:00:00Z',
      updated_at: '2026-05-03T18:10:00Z',
    })
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
    expect((await screen.findAllByText(/reconciliation/i)).length).toBeGreaterThan(0)
    expect(await screen.findByText(/negative product stock/i)).toBeInTheDocument()
    expect(await screen.findByText(/weekly ai reports/i)).toBeInTheDocument()
    expect(await screen.findByText(/weekly summary with coming week action priorities/i)).toBeInTheDocument()

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
      expect(apiMocks.getCloudReconciliation).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22, limit: 10 })
      )
      expect(apiMocks.getAIWeeklyReports).toHaveBeenCalledWith(
        expect.objectContaining({ organization_id: 22, limit: 5 })
      )
      expect(apiMocks.getAIWeeklyReportDeliveries).toHaveBeenCalledWith(55, {
        limit: 20,
      })
    })
  })

  it('generates a saved weekly manager report from the dashboard', async () => {
    const user = userEvent.setup()
    render(<CloudDashboardPage />)

    await screen.findByText(/weekly ai reports/i)
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => {
      expect(apiMocks.generateAIWeeklyReport).toHaveBeenCalledWith({
        organization_id: 22,
      })
    })
  })

  it('loads and updates persisted weekly report delivery history', async () => {
    const user = userEvent.setup()
    render(<CloudDashboardPage />)

    await screen.findByText(/weekly ai reports/i)
    expect(await screen.findByText(/telegram · 12345/i)).toBeInTheDocument()
    expect(await screen.findByText(/^skipped$/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^deliver$/i }))

    expect(await screen.findByText(/email · owner@example.com/i)).toBeInTheDocument()
    expect(await screen.findByText(/^sent$/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(apiMocks.deliverAIWeeklyReport).toHaveBeenCalledWith(55, {})
    })
  })

  it('allows admins to manage weekly report delivery settings', async () => {
    authMock.user = {
      ...authMock.user,
      role: 'admin',
    }
    const user = userEvent.setup()
    render(<CloudDashboardPage />)

    expect(await screen.findByText(/report delivery settings/i)).toBeInTheDocument()
    expect(apiMocks.getAIWeeklyReportDeliverySetting).toHaveBeenCalledWith({
      organization_id: 22,
    })

    const emailRecipients = await screen.findByLabelText(/email recipients/i)
    await user.clear(emailRecipients)
    await user.type(emailRecipients, 'owner@example.com\nops@example.com')
    await user.click(screen.getByLabelText(/telegram enabled/i))
    await user.type(screen.getByLabelText(/telegram chat ids/i), '12345')
    await user.click(screen.getByRole('button', { name: /save settings/i }))

    await waitFor(() => {
      expect(apiMocks.updateAIWeeklyReportDeliverySetting).toHaveBeenCalledWith({
        organization_id: 22,
        branch_id: null,
        email_enabled: true,
        email_recipients: ['owner@example.com', 'ops@example.com'],
        telegram_enabled: true,
        telegram_chat_ids: ['12345'],
        is_active: true,
      })
    })
    expect(await screen.findByText(/delivery settings saved/i)).toBeInTheDocument()
  })

  it('sends scoped AI manager chat requests and renders provider metadata', async () => {
    const user = userEvent.setup()
    render(<CloudDashboardPage />)

    await screen.findByText(/ai manager assistant/i)
    await user.click(screen.getByRole('button', { name: /which branch is performing best/i }))

    expect(await screen.findByText(/branch 2 is performing best/i)).toBeInTheDocument()
    expect((await screen.findAllByText(/provider: groq/i)).length).toBeGreaterThan(0)
    expect((await screen.findAllByText(/fallback: no/i)).length).toBeGreaterThan(0)

    await waitFor(() => {
      expect(apiMocks.chatWithAIManager).toHaveBeenCalledWith({
        message: 'Which branch is performing best?',
        organization_id: 22,
        period_days: 30,
      })
    })
  })
})

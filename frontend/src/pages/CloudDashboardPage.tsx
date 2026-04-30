import { type ComponentType, type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  FiActivity,
  FiAlertTriangle,
  FiBarChart2,
  FiCalendar,
  FiCheckCircle,
  FiCloud,
  FiDatabase,
  FiDollarSign,
  FiFileText,
  FiMessageSquare,
  FiRefreshCw,
  FiSend,
  FiShoppingCart,
  FiShield,
} from 'react-icons/fi'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../services/api'
import { useAuthStore } from '../stores/authStore'

interface CloudSalesSummary {
  organization_id: number
  branch_id: number | null
  sales_count: number
  total_revenue: number
  total_items: number
}

interface CloudBranchSalesSummary {
  branch_id: number
  sales_count: number
  total_revenue: number
  total_items: number
}

interface CloudInventoryMovementSummary {
  organization_id: number
  branch_id: number | null
  movement_count: number
  total_positive_quantity: number
  total_negative_quantity: number
  net_quantity_delta: number
}

interface CloudSyncHealth {
  organization_id: number
  branch_id: number | null
  ingested_event_count: number
  projected_event_count: number
  projection_failed_count: number
  duplicate_delivery_count: number
  last_received_at: string | null
  last_projected_at: string | null
}

interface CloudStockRiskSummary {
  organization_id: number
  branch_id: number | null
  low_stock_count: number
  out_of_stock_count: number
  near_expiry_batch_count: number
  expired_batch_count: number
  total_quantity_on_hand: number
  value_at_risk: number
  expiry_warning_days: number
}

interface CloudLowStockItem {
  branch_id: number
  product_id: number
  product_name: string
  sku: string
  total_stock: number
  low_stock_threshold: number
  units_needed: number
  status: string
}

interface CloudExpiryRiskItem {
  branch_id: number
  product_id: number
  product_name: string
  sku: string
  batch_id: number
  batch_number: string
  quantity: number
  expiry_date: string
  days_until_expiry: number
  value_at_risk: number
  status: string
}

interface CloudReconciliationIssue {
  severity: string
  issue_type: string
  branch_id: number | null
  product_id: number | null
  batch_id: number | null
  product_name: string | null
  batch_number: string | null
  expected_quantity: number | null
  actual_quantity: number | null
  delta: number | null
  message: string
}

interface CloudReconciliationSummary {
  organization_id: number
  branch_id: number | null
  product_snapshot_count: number
  batch_snapshot_count: number
  movement_fact_count: number
  projection_failed_count: number
  issue_count: number
  critical_issue_count: number
  high_issue_count: number
  medium_issue_count: number
  issues: CloudReconciliationIssue[]
}

interface AIWeeklyManagerReport {
  id: number
  organization_id: number
  branch_id: number | null
  generated_by_user_id: number | null
  performance_period_start: string
  performance_period_end: string
  action_period_start: string
  action_period_end: string
  title: string
  executive_summary: string
  sections: {
    coming_week_action_plan?: {
      priorities?: string[]
      risk_counts?: {
        out_of_stock_count?: number
        low_stock_count?: number
        expired_batch_count?: number
        near_expiry_batch_count?: number
        value_at_risk?: number
      }
    }
    sync_and_data_quality?: {
      reconciliation?: {
        issue_count?: number
        critical_issue_count?: number
        high_issue_count?: number
        medium_issue_count?: number
      }
    }
  }
  safety_notes: string[]
  provider: string
  model: string | null
  fallback_used: boolean
  generated_at: string
}

interface AIWeeklyReportDelivery {
  id: number
  report_id: number
  organization_id: number
  branch_id: number | null
  channel: string
  recipient: string
  status: string
  attempt_count: number
  error_message: string | null
  sent_at: string | null
  created_at: string
}

interface AIWeeklyReportDeliverySetting {
  id: number
  organization_id: number
  branch_id: number | null
  report_scope_key: string
  email_enabled: boolean
  email_recipients: string[]
  telegram_enabled: boolean
  telegram_chat_ids: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

interface DeliverySettingsFormState {
  email_enabled: boolean
  email_recipients: string
  telegram_enabled: boolean
  telegram_chat_ids: string
  is_active: boolean
}

interface AIManagerChatResponse {
  answer: string
  data_scope: {
    organization_id: number
    branch_id: number | null
    period_days: number
    sources: string[]
  }
  safety_notes: string[]
  provider: string
  model: string | null
  fallback_used: boolean
  refused: boolean
}

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  response?: AIManagerChatResponse
}

type LoadState = 'idle' | 'loading' | 'loaded'

const suggestedPrompts = [
  'Which branch is performing best?',
  'Summarize sync health.',
  'Is the cloud data reliable for decisions?',
  'Summarize inventory movement.',
  'What stock risks should I investigate today?',
  'What should I investigate today?',
]

const emptyDeliverySettingsForm: DeliverySettingsFormState = {
  email_enabled: false,
  email_recipients: '',
  telegram_enabled: false,
  telegram_chat_ids: '',
  is_active: true,
}

function formatCurrency(value: number) {
  return `GH₵ ${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatNumber(value: number) {
  return value.toLocaleString()
}

function formatDateTime(value: string | null) {
  if (!value) return 'No synced data'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function startDateForDays(days: number) {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString()
}

function listToText(values: string[] | undefined) {
  return (values ?? []).join('\n')
}

function textToList(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function deliveryFormFromSetting(setting: AIWeeklyReportDeliverySetting): DeliverySettingsFormState {
  return {
    email_enabled: setting.email_enabled,
    email_recipients: listToText(setting.email_recipients),
    telegram_enabled: setting.telegram_enabled,
    telegram_chat_ids: listToText(setting.telegram_chat_ids),
    is_active: setting.is_active,
  }
}

export default function CloudDashboardPage() {
  const { user } = useAuthStore()
  const defaultOrganizationId = user?.organization_id ? String(user.organization_id) : ''
  const [organizationInput, setOrganizationInput] = useState(defaultOrganizationId)
  const [selectedBranchId, setSelectedBranchId] = useState<string>(user?.branch_id ? String(user.branch_id) : 'all')
  const [periodDays, setPeriodDays] = useState(30)
  const [salesSummary, setSalesSummary] = useState<CloudSalesSummary | null>(null)
  const [branchSales, setBranchSales] = useState<CloudBranchSalesSummary[]>([])
  const [inventorySummary, setInventorySummary] = useState<CloudInventoryMovementSummary | null>(null)
  const [syncHealth, setSyncHealth] = useState<CloudSyncHealth | null>(null)
  const [stockRiskSummary, setStockRiskSummary] = useState<CloudStockRiskSummary | null>(null)
  const [lowStockItems, setLowStockItems] = useState<CloudLowStockItem[]>([])
  const [expiryRiskItems, setExpiryRiskItems] = useState<CloudExpiryRiskItem[]>([])
  const [reconciliationSummary, setReconciliationSummary] = useState<CloudReconciliationSummary | null>(null)
  const [weeklyReports, setWeeklyReports] = useState<AIWeeklyManagerReport[]>([])
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null)
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const [isDeliveringReport, setIsDeliveringReport] = useState(false)
  const [deliveryAttempts, setDeliveryAttempts] = useState<AIWeeklyReportDelivery[]>([])
  const [deliveryHistoryState, setDeliveryHistoryState] = useState<LoadState>('idle')
  const [deliveryError, setDeliveryError] = useState<string | null>(null)
  const [deliverySettings, setDeliverySettings] = useState<AIWeeklyReportDeliverySetting | null>(null)
  const [deliveryForm, setDeliveryForm] = useState<DeliverySettingsFormState>(emptyDeliverySettingsForm)
  const [deliverySettingsState, setDeliverySettingsState] = useState<LoadState>('idle')
  const [deliverySettingsError, setDeliverySettingsError] = useState<string | null>(null)
  const [deliverySettingsMessage, setDeliverySettingsMessage] = useState<string | null>(null)
  const [isSavingDeliverySettings, setIsSavingDeliverySettings] = useState(false)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [failedSections, setFailedSections] = useState<string[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)

  const organizationId = Number(organizationInput)
  const hasValidOrganization = Number.isInteger(organizationId) && organizationId > 0
  const branchId = selectedBranchId === 'all' ? undefined : Number(selectedBranchId)
  const isBranchLocked = user?.branch_id != null
  const isAdmin = user?.role === 'admin'

  const branchOptions = useMemo(() => {
    const ids = new Set<number>()
    branchSales.forEach((row) => ids.add(row.branch_id))
    if (user?.branch_id != null) ids.add(user.branch_id)
    return Array.from(ids).sort((a, b) => a - b)
  }, [branchSales, user?.branch_id])
  const selectedReport = weeklyReports.find((report) => report.id === selectedReportId) ?? weeklyReports[0] ?? null

  useEffect(() => {
    if (defaultOrganizationId) {
      setOrganizationInput(defaultOrganizationId)
    }
  }, [defaultOrganizationId])

  useEffect(() => {
    if (user?.branch_id != null) {
      setSelectedBranchId(String(user.branch_id))
    }
  }, [user?.branch_id])

  useEffect(() => {
    if (!hasValidOrganization) {
      return
    }

    loadCloudReports()
  }, [organizationInput, selectedBranchId, periodDays])

  useEffect(() => {
    if (!isAdmin || !hasValidOrganization) {
      setDeliverySettings(null)
      setDeliveryForm(emptyDeliverySettingsForm)
      setDeliverySettingsState('idle')
      return
    }

    loadDeliverySettings()
  }, [isAdmin, organizationInput, selectedBranchId])

  useEffect(() => {
    if (!selectedReport?.id) {
      setDeliveryAttempts([])
      setDeliveryHistoryState('idle')
      return
    }

    loadReportDeliveries(selectedReport.id)
  }, [selectedReport?.id])

  const loadCloudReports = async () => {
    setLoadState('loading')
    setFailedSections([])

    const baseParams = {
      organization_id: organizationId,
      start_at: startDateForDays(periodDays),
      ...(branchId ? { branch_id: branchId } : {}),
    }

    const syncParams = {
      organization_id: organizationId,
      ...(branchId ? { branch_id: branchId } : {}),
    }

    const results = await Promise.allSettled([
      api.getCloudSalesSummary(baseParams),
      api.getCloudBranchSales({
        organization_id: organizationId,
        start_at: baseParams.start_at,
      }),
      api.getCloudInventoryMovementSummary(baseParams),
      api.getCloudSyncHealth(syncParams),
      api.getCloudStockRiskSummary({
        ...syncParams,
        expiry_warning_days: 90,
      }),
      api.getCloudLowStock({
        ...syncParams,
        limit: 10,
      }),
      api.getCloudExpiryRisk({
        ...syncParams,
        days: 90,
        limit: 10,
      }),
      api.getCloudReconciliation({
        ...syncParams,
        limit: 10,
      }),
      api.getAIWeeklyReports({
        ...syncParams,
        limit: 5,
      }),
    ])

    const failures: string[] = []
    const [
      salesResult,
      branchResult,
      inventoryResult,
      syncResult,
      stockRiskResult,
      lowStockResult,
      expiryRiskResult,
      reconciliationResult,
      weeklyReportsResult,
    ] = results

    if (salesResult.status === 'fulfilled') {
      setSalesSummary(salesResult.value)
    } else {
      setSalesSummary(null)
      failures.push('Sales summary')
    }

    if (branchResult.status === 'fulfilled') {
      setBranchSales(branchResult.value)
    } else {
      setBranchSales([])
      failures.push('Branch sales')
    }

    if (inventoryResult.status === 'fulfilled') {
      setInventorySummary(inventoryResult.value)
    } else {
      setInventorySummary(null)
      failures.push('Inventory movements')
    }

    if (syncResult.status === 'fulfilled') {
      setSyncHealth(syncResult.value)
    } else {
      setSyncHealth(null)
      failures.push('Sync health')
    }

    if (stockRiskResult.status === 'fulfilled') {
      setStockRiskSummary(stockRiskResult.value)
    } else {
      setStockRiskSummary(null)
      failures.push('Stock risk summary')
    }

    if (lowStockResult.status === 'fulfilled') {
      setLowStockItems(lowStockResult.value)
    } else {
      setLowStockItems([])
      failures.push('Low stock')
    }

    if (expiryRiskResult.status === 'fulfilled') {
      setExpiryRiskItems(expiryRiskResult.value)
    } else {
      setExpiryRiskItems([])
      failures.push('Expiry risk')
    }

    if (reconciliationResult.status === 'fulfilled') {
      setReconciliationSummary(reconciliationResult.value)
    } else {
      setReconciliationSummary(null)
      failures.push('Reconciliation')
    }

    if (weeklyReportsResult.status === 'fulfilled') {
      setWeeklyReports(weeklyReportsResult.value)
      setSelectedReportId((current) => current ?? weeklyReportsResult.value[0]?.id ?? null)
    } else {
      setWeeklyReports([])
      failures.push('Weekly reports')
    }

    setFailedSections(failures)
    setLoadState('loaded')
  }

  const isLoading = loadState === 'loading'
  const chartRows = branchSales.map((row) => ({
    branch: `Branch ${row.branch_id}`,
    revenue: row.total_revenue,
    sales: row.sales_count,
  }))
  const hasCriticalReconciliation =
    (reconciliationSummary?.critical_issue_count ?? 0) > 0 || (reconciliationSummary?.high_issue_count ?? 0) > 0

  const generateWeeklyReport = async () => {
    if (!hasValidOrganization || isGeneratingReport) return
    setIsGeneratingReport(true)
    setReportError(null)
    try {
      const report: AIWeeklyManagerReport = await api.generateAIWeeklyReport({
        organization_id: organizationId,
        ...(branchId ? { branch_id: branchId } : {}),
      })
      setWeeklyReports((current) => [report, ...current.filter((item) => item.id !== report.id)].slice(0, 5))
      setSelectedReportId(report.id)
    } catch (error) {
      setReportError('Weekly report generation failed.')
    } finally {
      setIsGeneratingReport(false)
    }
  }

  const deliverSelectedReport = async () => {
    if (!selectedReport || isDeliveringReport) return
    setIsDeliveringReport(true)
    setDeliveryError(null)
    try {
      const deliveries: AIWeeklyReportDelivery[] = await api.deliverAIWeeklyReport(selectedReport.id, {})
      setDeliveryAttempts((current) => [
        ...deliveries,
        ...current.filter((existing) => !deliveries.some((delivery) => delivery.id === existing.id)),
      ].slice(0, 20))
    } catch (error) {
      setDeliveryError('Weekly report delivery failed.')
    } finally {
      setIsDeliveringReport(false)
    }
  }

  const loadReportDeliveries = async (reportId: number) => {
    setDeliveryHistoryState('loading')
    setDeliveryError(null)
    try {
      const deliveries: AIWeeklyReportDelivery[] = await api.getAIWeeklyReportDeliveries(reportId, {
        limit: 20,
      })
      setDeliveryAttempts(deliveries)
    } catch (error) {
      setDeliveryAttempts([])
      setDeliveryError('Delivery history could not be loaded.')
    } finally {
      setDeliveryHistoryState('loaded')
    }
  }

  const loadDeliverySettings = async () => {
    setDeliverySettingsState('loading')
    setDeliverySettingsError(null)
    setDeliverySettingsMessage(null)

    try {
      const setting: AIWeeklyReportDeliverySetting = await api.getAIWeeklyReportDeliverySetting({
        organization_id: organizationId,
        ...(branchId ? { branch_id: branchId } : {}),
      })
      setDeliverySettings(setting)
      setDeliveryForm(deliveryFormFromSetting(setting))
    } catch (error: any) {
      if (error?.response?.status === 404) {
        setDeliverySettings(null)
        setDeliveryForm(emptyDeliverySettingsForm)
      } else {
        setDeliverySettingsError('Delivery settings could not be loaded.')
      }
    } finally {
      setDeliverySettingsState('loaded')
    }
  }

  const saveDeliverySettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!hasValidOrganization || isSavingDeliverySettings) return

    setIsSavingDeliverySettings(true)
    setDeliverySettingsError(null)
    setDeliverySettingsMessage(null)

    try {
      const setting: AIWeeklyReportDeliverySetting = await api.updateAIWeeklyReportDeliverySetting({
        organization_id: organizationId,
        ...(branchId ? { branch_id: branchId } : { branch_id: null }),
        email_enabled: deliveryForm.email_enabled,
        email_recipients: textToList(deliveryForm.email_recipients),
        telegram_enabled: deliveryForm.telegram_enabled,
        telegram_chat_ids: textToList(deliveryForm.telegram_chat_ids),
        is_active: deliveryForm.is_active,
      })
      setDeliverySettings(setting)
      setDeliveryForm(deliveryFormFromSetting(setting))
      setDeliverySettingsMessage('Delivery settings saved.')
    } catch (error) {
      setDeliverySettingsError('Delivery settings could not be saved.')
    } finally {
      setIsSavingDeliverySettings(false)
    }
  }

  const sendAIMessage = async (message: string) => {
    const trimmedMessage = message.trim()
    if (!trimmedMessage || !hasValidOrganization || isChatLoading) return

    const userMessage: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: trimmedMessage,
    }
    setChatMessages((current) => [...current, userMessage])
    setChatInput('')
    setChatError(null)
    setIsChatLoading(true)

    try {
      const response: AIManagerChatResponse = await api.chatWithAIManager({
        message: trimmedMessage,
        organization_id: organizationId,
        ...(branchId ? { branch_id: branchId } : {}),
        period_days: periodDays,
      })
      setChatMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: 'assistant',
          content: response.answer,
          response,
        },
      ])
    } catch (error) {
      setChatError('AI assistant request failed.')
    } finally {
      setIsChatLoading(false)
    }
  }

  const handleAISubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    sendAIMessage(chatInput)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Cloud Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Synced branch reporting and cloud sync health
          </p>
        </div>

        <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800 md:flex-row md:items-end">
          <label className="block">
            <span className="label">Organization ID</span>
            <input
              className="input h-10 w-40"
              inputMode="numeric"
              value={organizationInput}
              onChange={(event) => setOrganizationInput(event.target.value)}
              disabled={user?.organization_id != null}
            />
          </label>

          <label className="block">
            <span className="label">Branch</span>
            <select
              className="input h-10 w-44"
              value={selectedBranchId}
              onChange={(event) => setSelectedBranchId(event.target.value)}
              disabled={isBranchLocked}
            >
              {!isBranchLocked && <option value="all">All branches</option>}
              {branchOptions.map((id) => (
                <option key={id} value={id}>
                  Branch {id}
                </option>
              ))}
            </select>
          </label>

          <div>
            <span className="label">Period</span>
            <div className="flex gap-2">
              {[7, 30, 90].map((days) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => setPeriodDays(days)}
                  className={`h-10 rounded-lg px-3 text-sm font-medium transition-colors ${
                    periodDays === days
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600'
                  }`}
                >
                  {days}D
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={loadCloudReports}
            disabled={!hasValidOrganization || isLoading}
            className="btn-secondary flex h-10 items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FiRefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {!hasValidOrganization && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-100">
          Organization assignment is required before cloud reports can be loaded.
        </div>
      )}

      {failedSections.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-100">
          Failed sections: {failedSections.join(', ')}
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="card h-32 p-6 skeleton" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            title="Cloud Revenue"
            value={formatCurrency(salesSummary?.total_revenue ?? 0)}
            detail={`${formatNumber(salesSummary?.sales_count ?? 0)} sales`}
            icon={FiDollarSign}
            tone="green"
          />
          <MetricCard
            title="Items Sold"
            value={formatNumber(salesSummary?.total_items ?? 0)}
            detail={`${periodDays} day synced window`}
            icon={FiShoppingCart}
            tone="blue"
          />
          <MetricCard
            title="Net Stock Movement"
            value={formatNumber(inventorySummary?.net_quantity_delta ?? 0)}
            detail={`${formatNumber(inventorySummary?.movement_count ?? 0)} movement rows`}
            icon={FiDatabase}
            tone="indigo"
          />
          <MetricCard
            title="Projection Failures"
            value={formatNumber(syncHealth?.projection_failed_count ?? 0)}
            detail={`${formatNumber(syncHealth?.duplicate_delivery_count ?? 0)} duplicate deliveries`}
            icon={syncHealth?.projection_failed_count ? FiAlertTriangle : FiActivity}
            tone={syncHealth?.projection_failed_count ? 'red' : 'slate'}
          />
          <MetricCard
            title="Reconciliation"
            value={formatNumber(reconciliationSummary?.issue_count ?? 0)}
            detail={`${formatNumber(reconciliationSummary?.critical_issue_count ?? 0)} critical · ${formatNumber(reconciliationSummary?.high_issue_count ?? 0)} high`}
            icon={hasCriticalReconciliation ? FiAlertTriangle : FiShield}
            tone={hasCriticalReconciliation ? 'red' : 'slate'}
          />
          <MetricCard
            title="Stock Risk"
            value={formatNumber((stockRiskSummary?.out_of_stock_count ?? 0) + (stockRiskSummary?.low_stock_count ?? 0))}
            detail={`${formatNumber(stockRiskSummary?.expired_batch_count ?? 0)} expired batches`}
            icon={FiAlertTriangle}
            tone={(stockRiskSummary?.out_of_stock_count || stockRiskSummary?.expired_batch_count) ? 'red' : 'slate'}
          />
          <MetricCard
            title="Expiry Value Risk"
            value={formatCurrency(stockRiskSummary?.value_at_risk ?? 0)}
            detail={`${formatNumber(stockRiskSummary?.near_expiry_batch_count ?? 0)} near-expiry batches`}
            icon={FiCalendar}
            tone={(stockRiskSummary?.near_expiry_batch_count || stockRiskSummary?.expired_batch_count) ? 'red' : 'slate'}
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="card p-6 xl:col-span-2">
          <div className="mb-6 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Branch Sales
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Revenue by synced branch
              </p>
            </div>
            <FiBarChart2 className="h-5 w-5 text-gray-400" />
          </div>

          {chartRows.length > 0 ? (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartRows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="branch" />
                  <YAxis />
                  <Tooltip
                    formatter={(value, name) => {
                      if (name === 'revenue') return [formatCurrency(Number(value)), 'Revenue']
                      return [formatNumber(Number(value)), 'Sales']
                    }}
                  />
                  <Bar dataKey="revenue" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="sales" fill="#059669" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex h-80 items-center justify-center rounded-lg border border-dashed border-gray-300 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
              No branch sales available
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Sync Health
              </h2>
              <FiCloud className="h-5 w-5 text-gray-400" />
            </div>
            <div className="space-y-4">
              <StatusRow label="Ingested events" value={formatNumber(syncHealth?.ingested_event_count ?? 0)} />
              <StatusRow label="Projected events" value={formatNumber(syncHealth?.projected_event_count ?? 0)} />
              <StatusRow label="Last received" value={formatDateTime(syncHealth?.last_received_at ?? null)} />
              <StatusRow label="Last projected" value={formatDateTime(syncHealth?.last_projected_at ?? null)} />
            </div>
          </div>

          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Stock Movement
              </h2>
              <FiCalendar className="h-5 w-5 text-gray-400" />
            </div>
            <div className="space-y-4">
              <StatusRow label="Positive quantity" value={formatNumber(inventorySummary?.total_positive_quantity ?? 0)} />
              <StatusRow label="Negative quantity" value={formatNumber(inventorySummary?.total_negative_quantity ?? 0)} />
              <StatusRow label="Net quantity" value={formatNumber(inventorySummary?.net_quantity_delta ?? 0)} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ReconciliationPanel reconciliation={reconciliationSummary} />
        <WeeklyReportsPanel
          reports={weeklyReports}
          selectedReport={selectedReport}
          selectedReportId={selectedReportId}
          onSelectReport={setSelectedReportId}
          onGenerate={generateWeeklyReport}
          onDeliver={deliverSelectedReport}
          isGenerating={isGeneratingReport}
          isDelivering={isDeliveringReport}
          error={reportError}
          deliveryError={deliveryError}
          deliveryAttempts={deliveryAttempts}
          deliveryHistoryState={deliveryHistoryState}
          disabled={!hasValidOrganization}
        />
      </div>

      {isAdmin && (
        <DeliverySettingsPanel
          form={deliveryForm}
          setting={deliverySettings}
          state={deliverySettingsState}
          error={deliverySettingsError}
          message={deliverySettingsMessage}
          disabled={!hasValidOrganization || isSavingDeliverySettings}
          isSaving={isSavingDeliverySettings}
          onSubmit={saveDeliverySettings}
          onChange={setDeliveryForm}
        />
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <RiskTable
          title="Low Stock"
          emptyText="No low-stock products in the current scope"
          rows={lowStockItems.map((item) => ({
            key: `${item.branch_id}-${item.product_id}`,
            primary: item.product_name,
            secondary: `${item.sku} · Branch ${item.branch_id}`,
            value: `${item.total_stock} on hand`,
            status: item.status === 'out_of_stock' ? 'Out of stock' : 'Low stock',
          }))}
        />
        <RiskTable
          title="Expiry Risk"
          emptyText="No expiry risk in the current scope"
          rows={expiryRiskItems.map((item) => ({
            key: `${item.branch_id}-${item.batch_id}`,
            primary: item.product_name,
            secondary: `${item.batch_number} · Branch ${item.branch_id}`,
            value: `${item.days_until_expiry} days`,
            status: item.status === 'expired' ? 'Expired' : formatCurrency(item.value_at_risk),
          }))}
        />
      </div>

      <div className="card p-6">
        <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
              <FiMessageSquare className="h-5 w-5 text-primary-600 dark:text-primary-400" />
              AI Manager Assistant
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Read-only answers from approved cloud reporting data
            </p>
          </div>
          <div className="rounded-lg bg-gray-100 px-3 py-2 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">
            Scope: Org {hasValidOrganization ? organizationId : '-'} · {branchId ? `Branch ${branchId}` : 'Permitted branches'} · {periodDays}D
          </div>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {suggestedPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => sendAIMessage(prompt)}
              disabled={!hasValidOrganization || isChatLoading}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="mb-4 max-h-96 space-y-4 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900">
          {chatMessages.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              Ask about branch performance, sync health, or inventory movement.
            </div>
          ) : (
            chatMessages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-3xl rounded-lg px-4 py-3 text-sm ${
                    message.role === 'user'
                      ? 'bg-primary-600 text-white'
                      : 'border border-gray-200 bg-white text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100'
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                  {message.response && (
                    <div className="mt-3 space-y-2 border-t border-gray-200 pt-3 text-xs text-gray-500 dark:border-gray-700 dark:text-gray-400">
                      <div className="flex flex-wrap gap-x-4 gap-y-1">
                        <span>Provider: {message.response.provider}</span>
                        <span>Model: {message.response.model || 'not configured'}</span>
                        <span>Fallback: {message.response.fallback_used ? 'yes' : 'no'}</span>
                        <span>Refused: {message.response.refused ? 'yes' : 'no'}</span>
                      </div>
                      <div>
                        Data scope: Org {message.response.data_scope.organization_id}, {message.response.data_scope.branch_id ? `Branch ${message.response.data_scope.branch_id}` : 'permitted branches'}, {message.response.data_scope.period_days}D
                      </div>
                      <ul className="space-y-1">
                        {message.response.safety_notes.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {isChatLoading && (
            <div className="text-sm text-gray-500 dark:text-gray-400">
              Assistant is checking approved report data...
            </div>
          )}
        </div>

        {chatError && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-100">
            {chatError}
          </div>
        )}

        <form onSubmit={handleAISubmit} className="flex flex-col gap-3 md:flex-row">
          <input
            className="input min-h-11 flex-1"
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            placeholder="Ask the assistant about synced sales, branches, inventory movement, or sync health"
            disabled={!hasValidOrganization || isChatLoading}
          />
          <button
            type="submit"
            disabled={!hasValidOrganization || !chatInput.trim() || isChatLoading}
            className="btn-primary flex min-h-11 items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FiSend className="h-4 w-4" />
            Send
          </button>
        </form>
      </div>
    </div>
  )
}

interface MetricCardProps {
  title: string
  value: string
  detail: string
  icon: ComponentType<{ className?: string }>
  tone: 'green' | 'blue' | 'indigo' | 'red' | 'slate'
}

function MetricCard({ title, value, detail, icon: Icon, tone }: MetricCardProps) {
  const toneClasses = {
    green: 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-300',
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300',
    indigo: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-300',
    red: 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300',
    slate: 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300',
  }

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <p className="mt-2 truncate text-2xl font-bold text-gray-900 dark:text-gray-100">
            {value}
          </p>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{detail}</p>
        </div>
        <div className={`rounded-lg p-3 ${toneClasses[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-3 last:border-0 last:pb-0 dark:border-gray-700">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-right text-sm font-semibold text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  )
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
}

function formatIssueType(value: string) {
  return value.replace(/_/g, ' ')
}

function ReconciliationPanel({ reconciliation }: { reconciliation: CloudReconciliationSummary | null }) {
  const issues = reconciliation?.issues ?? []
  const hasHighRisk = (reconciliation?.critical_issue_count ?? 0) > 0 || (reconciliation?.high_issue_count ?? 0) > 0

  return (
    <div className="card p-6">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
            <FiShield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
            Reconciliation
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Projection consistency checks
          </p>
        </div>
        <span className={`rounded-lg px-3 py-1 text-xs font-semibold ${
          hasHighRisk
            ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300'
            : 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-300'
        }`}>
          {hasHighRisk ? 'Review required' : 'No high risk'}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3">
        <MiniStat label="Critical" value={reconciliation?.critical_issue_count ?? 0} tone="red" />
        <MiniStat label="High" value={reconciliation?.high_issue_count ?? 0} tone="amber" />
        <MiniStat label="Medium" value={reconciliation?.medium_issue_count ?? 0} tone="slate" />
      </div>

      {issues.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
          No reconciliation issues in the current scope
        </div>
      ) : (
        <div className="max-h-80 divide-y divide-gray-100 overflow-y-auto dark:divide-gray-700">
          {issues.map((issue, index) => (
            <div key={`${issue.issue_type}-${issue.branch_id}-${issue.product_id}-${issue.batch_id}-${index}`} className="py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold capitalize text-gray-900 dark:text-gray-100">
                    {formatIssueType(issue.issue_type)}
                  </p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{issue.message}</p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Branch {issue.branch_id ?? '-'} · Product {issue.product_id ?? '-'} · Batch {issue.batch_id ?? '-'}
                  </p>
                </div>
                <span className={`rounded-lg px-2 py-1 text-xs font-semibold capitalize ${
                  issue.severity === 'critical'
                    ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300'
                    : issue.severity === 'high'
                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300'
                      : 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300'
                }`}>
                  {issue.severity}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function WeeklyReportsPanel({
  reports,
  selectedReport,
  selectedReportId,
  onSelectReport,
  onGenerate,
  onDeliver,
  isGenerating,
  isDelivering,
  error,
  deliveryError,
  deliveryAttempts,
  deliveryHistoryState,
  disabled,
}: {
  reports: AIWeeklyManagerReport[]
  selectedReport: AIWeeklyManagerReport | null
  selectedReportId: number | null
  onSelectReport: (id: number) => void
  onGenerate: () => void
  onDeliver: () => void
  isGenerating: boolean
  isDelivering: boolean
  error: string | null
  deliveryError: string | null
  deliveryAttempts: AIWeeklyReportDelivery[]
  deliveryHistoryState: LoadState
  disabled: boolean
}) {
  const riskCounts = selectedReport?.sections.coming_week_action_plan?.risk_counts
  const reconciliation = selectedReport?.sections.sync_and_data_quality?.reconciliation

  return (
    <div className="card p-6">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
            <FiFileText className="h-5 w-5 text-primary-600 dark:text-primary-400" />
            Weekly AI Reports
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Saved Sunday manager reports
          </p>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={disabled || isGenerating}
          className="btn-secondary flex h-10 items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <FiRefreshCw className={`h-4 w-4 ${isGenerating ? 'animate-spin' : ''}`} />
          Generate
        </button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onDeliver}
          disabled={disabled || !selectedReport || isDelivering}
          className="btn-primary flex h-10 items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <FiSend className={`h-4 w-4 ${isDelivering ? 'animate-pulse' : ''}`} />
          Deliver
        </button>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          Uses tenant-scoped email and Telegram settings
        </span>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-100">
          {error}
        </div>
      )}

      {deliveryError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-100">
          {deliveryError}
        </div>
      )}

      {reports.length > 0 && (
        <div className="mb-4">
          <label className="block">
            <span className="label">Report</span>
            <select
              className="input h-10 w-full"
              value={selectedReportId ?? reports[0].id}
              onChange={(event) => onSelectReport(Number(event.target.value))}
            >
              {reports.map((report) => (
                <option key={report.id} value={report.id}>
                  {formatDate(report.action_period_start)} to {formatDate(report.action_period_end)}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {!selectedReport ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
          No saved weekly reports in the current scope
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{selectedReport.title}</h3>
            <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
              {selectedReport.executive_summary}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <MiniStat label="Out of stock" value={riskCounts?.out_of_stock_count ?? 0} tone="red" />
            <MiniStat label="Low stock" value={riskCounts?.low_stock_count ?? 0} tone="amber" />
            <MiniStat label="Expired" value={riskCounts?.expired_batch_count ?? 0} tone="red" />
            <MiniStat label="Recon issues" value={reconciliation?.issue_count ?? 0} tone="slate" />
          </div>

          <div className="rounded-lg bg-gray-50 p-3 text-xs text-gray-600 dark:bg-gray-900 dark:text-gray-300">
            Provider: {selectedReport.provider} · Model: {selectedReport.model || 'not configured'} · Fallback: {selectedReport.fallback_used ? 'yes' : 'no'} · Generated: {formatDateTime(selectedReport.generated_at)}
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                Delivery History
              </h4>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {deliveryHistoryState === 'loading' ? 'Loading...' : `${deliveryAttempts.length} attempts`}
              </span>
            </div>

            {deliveryAttempts.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 p-4 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                No delivery attempts recorded for this report
              </div>
            ) : (
              <div className="max-h-64 divide-y divide-gray-100 overflow-y-auto rounded-lg border border-gray-200 dark:divide-gray-700 dark:border-gray-700">
                {deliveryAttempts.map((delivery) => (
                  <div key={delivery.id} className="flex items-start justify-between gap-3 p-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold capitalize text-gray-900 dark:text-gray-100">
                        {delivery.channel} · {delivery.recipient}
                      </p>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Attempts: {delivery.attempt_count} · {delivery.error_message || (delivery.sent_at ? `Sent ${formatDateTime(delivery.sent_at)}` : `Recorded ${formatDateTime(delivery.created_at)}`)}
                      </p>
                    </div>
                    <span className={`rounded-lg px-2 py-1 text-xs font-semibold capitalize ${
                      delivery.status === 'sent'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-300'
                        : delivery.status === 'failed'
                          ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300'
                          : 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300'
                    }`}>
                      {delivery.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function DeliverySettingsPanel({
  form,
  setting,
  state,
  error,
  message,
  disabled,
  isSaving,
  onSubmit,
  onChange,
}: {
  form: DeliverySettingsFormState
  setting: AIWeeklyReportDeliverySetting | null
  state: LoadState
  error: string | null
  message: string | null
  disabled: boolean
  isSaving: boolean
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onChange: (next: DeliverySettingsFormState) => void
}) {
  const isLoading = state === 'loading'

  return (
    <div className="card p-6">
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
            <FiSend className="h-5 w-5 text-primary-600 dark:text-primary-400" />
            Report Delivery Settings
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Tenant-scoped Sunday report recipients
          </p>
        </div>
        <div className="rounded-lg bg-gray-100 px-3 py-2 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">
          {setting ? `Scope: ${setting.report_scope_key}` : 'No saved scope'}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-100">
          {error}
        </div>
      )}

      {message && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-900/20 dark:text-green-100">
          <FiCheckCircle className="h-4 w-4" />
          {message}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
            <input
              type="checkbox"
              checked={form.email_enabled}
              onChange={(event) => onChange({ ...form, email_enabled: event.target.checked })}
              disabled={disabled || isLoading}
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm font-medium text-gray-800 dark:text-gray-100">Email enabled</span>
          </label>

          <label className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
            <input
              type="checkbox"
              checked={form.telegram_enabled}
              onChange={(event) => onChange({ ...form, telegram_enabled: event.target.checked })}
              disabled={disabled || isLoading}
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm font-medium text-gray-800 dark:text-gray-100">Telegram enabled</span>
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label className="block">
            <span className="label">Email recipients</span>
            <textarea
              className="input min-h-28 resize-y"
              value={form.email_recipients}
              onChange={(event) => onChange({ ...form, email_recipients: event.target.value })}
              disabled={disabled || isLoading}
            />
          </label>

          <label className="block">
            <span className="label">Telegram chat IDs</span>
            <textarea
              className="input min-h-28 resize-y"
              value={form.telegram_chat_ids}
              onChange={(event) => onChange({ ...form, telegram_chat_ids: event.target.value })}
              disabled={disabled || isLoading}
            />
          </label>
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => onChange({ ...form, is_active: event.target.checked })}
              disabled={disabled || isLoading}
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm font-medium text-gray-800 dark:text-gray-100">Active configuration</span>
          </label>

          <button
            type="submit"
            disabled={disabled || isLoading}
            className="btn-primary flex h-10 items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FiCheckCircle className={`h-4 w-4 ${isSaving ? 'animate-pulse' : ''}`} />
            Save settings
          </button>
        </div>
      </form>
    </div>
  )
}

function MiniStat({ label, value, tone }: { label: string; value: number; tone: 'red' | 'amber' | 'slate' }) {
  const classes = {
    red: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300',
    amber: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300',
    slate: 'bg-slate-50 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300',
  }

  return (
    <div className={`rounded-lg p-3 ${classes[tone]}`}>
      <p className="text-xs font-medium">{label}</p>
      <p className="mt-1 text-xl font-bold">{formatNumber(value)}</p>
    </div>
  )
}

interface RiskTableRow {
  key: string
  primary: string
  secondary: string
  value: string
  status: string
}

function RiskTable({ title, emptyText, rows }: { title: string; emptyText: string; rows: RiskTableRow[] }) {
  return (
    <div className="card p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
        <FiAlertTriangle className="h-5 w-5 text-gray-400" />
      </div>
      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
          {emptyText}
        </div>
      ) : (
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {rows.map((row) => (
            <div key={row.key} className="grid grid-cols-[1fr_auto] gap-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-gray-900 dark:text-gray-100">{row.primary}</p>
                <p className="truncate text-xs text-gray-500 dark:text-gray-400">{row.secondary}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{row.value}</p>
                <p className="text-xs text-red-600 dark:text-red-300">{row.status}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

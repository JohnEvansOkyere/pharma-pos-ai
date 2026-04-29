import { type ComponentType, type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  FiActivity,
  FiAlertTriangle,
  FiBarChart2,
  FiCalendar,
  FiCloud,
  FiDatabase,
  FiDollarSign,
  FiMessageSquare,
  FiRefreshCw,
  FiSend,
  FiShoppingCart,
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
  'Summarize inventory movement.',
  'What stock risks should I investigate today?',
  'What should I investigate today?',
]

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

  const branchOptions = useMemo(() => {
    const ids = new Set<number>()
    branchSales.forEach((row) => ids.add(row.branch_id))
    if (user?.branch_id != null) ids.add(user.branch_id)
    return Array.from(ids).sort((a, b) => a - b)
  }, [branchSales, user?.branch_id])

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
    ])

    const failures: string[] = []
    const [salesResult, branchResult, inventoryResult, syncResult, stockRiskResult, lowStockResult, expiryRiskResult] = results

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

    setFailedSections(failures)
    setLoadState('loaded')
  }

  const isLoading = loadState === 'loading'
  const chartRows = branchSales.map((row) => ({
    branch: `Branch ${row.branch_id}`,
    revenue: row.total_revenue,
    sales: row.sales_count,
  }))

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

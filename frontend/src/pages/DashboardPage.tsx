import { useState, useEffect } from 'react'
import { api } from '../services/api'
import {
  FiDollarSign,
  FiTrendingUp,
  FiPackage,
  FiAlertCircle,
  FiShoppingCart,
  FiCreditCard,
  FiCalendar,
} from 'react-icons/fi'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

interface KPIs {
  total_sales_today: number
  profit_today: number
  inventory_value: number
  items_near_expiry: number
  low_stock_items: number
  total_products: number
  total_sales_count: number
}

interface RevenueAnalysis {
  daily_revenue: number
  daily_transactions: number
  weekly_revenue: number
  weekly_transactions: number
  monthly_revenue: number
  monthly_transactions: number
  average_basket_value: number
}

interface FinancialKPIs {
  total_revenue: number
  gross_profit: number
  net_profit: number
  profit_margin: number
  average_basket_value: number
  total_transactions: number
  outstanding_credit: number
  credit_sales_count: number
}

interface ExpiringProduct {
  product_id: number
  product_name: string
  sku: string
  dosage_form: string
  strength: string
  batch_number: string
  batch_quantity: number
  expiry_date: string
  days_until_expiry: number
  value_at_risk: number
}

interface LowStockItem {
  product_id: number
  product_name: string
  sku: string
  dosage_form: string
  strength: string
  current_stock: number
  low_stock_threshold: number
  reorder_level: number
  units_needed: number
  status: 'out_of_stock' | 'low_stock'
}

interface OverstockItem {
  product_id: number
  product_name: string
  sku: string
  dosage_form: string
  strength: string
  total_stock: number
  reorder_level: number
  excess_stock: number
  capital_tied: number
}

interface ProfitByCategory {
  category_id: number
  category_name: string
  total_revenue: number
  total_profit: number
  profit_margin: number
  items_sold: number
}

export default function DashboardPage() {
  const [kpis, setKpis] = useState<KPIs | null>(null)
  const [salesTrend, setSalesTrend] = useState<any[]>([])
  const [fastMoving, setFastMoving] = useState<any[]>([])
  const [slowMoving, setSlowMoving] = useState<any[]>([])
  const [revenueAnalysis, setRevenueAnalysis] = useState<RevenueAnalysis | null>(null)
  const [financialKPIs, setFinancialKPIs] = useState<FinancialKPIs | null>(null)
  const [expiringProducts, setExpiringProducts] = useState<ExpiringProduct[]>([])
  const [lowStockItems, setLowStockItems] = useState<LowStockItem[]>([])
  const [overstockItems, setOverstockItems] = useState<OverstockItem[]>([])
  const [profitByCategory, setProfitByCategory] = useState<ProfitByCategory[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [expiryDays, setExpiryDays] = useState(30)
  const [analysisPeriod, setAnalysisPeriod] = useState(30) // Days for financial analysis
  const [trendDays, setTrendDays] = useState(7) // Days for sales trend chart
  const [useCustomDates, setUseCustomDates] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  useEffect(() => {
    loadDashboardData()
  }, [expiryDays, analysisPeriod, trendDays, useCustomDates, startDate, endDate])

  const calculateDaysFromDateRange = () => {
    if (useCustomDates && startDate && endDate) {
      const start = new Date(startDate)
      const end = new Date(endDate)
      const diffTime = Math.abs(end.getTime() - start.getTime())
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
      return diffDays
    }
    return analysisPeriod
  }

  const getDateRangeLabel = () => {
    if (useCustomDates && startDate && endDate) {
      const start = new Date(startDate).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      const end = new Date(endDate).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      return `${start} - ${end}`
    }
    return `Last ${analysisPeriod} Days`
  }

  const loadDashboardData = async () => {
    setIsLoading(true)
    try {
      const effectiveDays = calculateDaysFromDateRange()

      const [
        kpisData,
        trendData,
        fastMovingData,
        slowMovingData,
        revenueData,
        financialData,
        expiringData,
        lowStockData,
        overstockData,
        profitCategoryData,
      ] = await Promise.all([
        api.getDashboardKPIs(),
        api.getSalesTrend({ days: trendDays }),
        api.getFastMovingProducts({ limit: 5, days: effectiveDays }),
        api.getSlowMovingProducts({ limit: 5, days: effectiveDays }),
        api.getRevenueAnalysis(),
        api.getFinancialKPIs({ days: effectiveDays }),
        api.getExpiringProducts({ days: expiryDays, limit: 10 }),
        api.getLowStockItems({ limit: 50 }),
        api.getOverstockItems(),
        api.getProfitByCategory({ days: effectiveDays }),
      ])

      setKpis(kpisData)
      setSalesTrend(trendData)
      setFastMoving(fastMovingData)
      setSlowMoving(slowMovingData)
      setRevenueAnalysis(revenueData)
      setFinancialKPIs(financialData)
      setExpiringProducts(expiringData)
      setLowStockItems(lowStockData)
      setOverstockItems(overstockData)
      setProfitByCategory(profitCategoryData)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-6 skeleton h-32" />
          ))}
        </div>
      </div>
    )
  }

  const COLORS = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

  return (
    <div className="space-y-6">
      {/* Page Header with Date Filter */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Comprehensive overview of your pharmacy operations and financial performance
          </p>
        </div>

        {/* Analysis Period Filter */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex items-center gap-2">
              <FiCalendar className="text-gray-500 dark:text-gray-400" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Analysis Period:</span>
            </div>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => {
                  setUseCustomDates(false)
                  setAnalysisPeriod(7)
                }}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  !useCustomDates && analysisPeriod === 7
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                7 Days
              </button>
              <button
                onClick={() => {
                  setUseCustomDates(false)
                  setAnalysisPeriod(30)
                }}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  !useCustomDates && analysisPeriod === 30
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                30 Days
              </button>
              <button
                onClick={() => {
                  setUseCustomDates(false)
                  setAnalysisPeriod(90)
                }}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  !useCustomDates && analysisPeriod === 90
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                90 Days
              </button>
              <button
                onClick={() => {
                  setUseCustomDates(false)
                  setAnalysisPeriod(365)
                }}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  !useCustomDates && analysisPeriod === 365
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                1 Year
              </button>
              <button
                onClick={() => setUseCustomDates(!useCustomDates)}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  useCustomDates
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                Custom Range
              </button>
            </div>
          </div>

          {/* Custom Date Range Inputs */}
          {useCustomDates && (
            <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
              <div className="flex items-center gap-2">
                <label htmlFor="startDate" className="text-sm text-gray-600 dark:text-gray-400">
                  From:
                </label>
                <input
                  type="date"
                  id="startDate"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
              <div className="flex items-center gap-2">
                <label htmlFor="endDate" className="text-sm text-gray-600 dark:text-gray-400">
                  To:
                </label>
                <input
                  type="date"
                  id="endDate"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
              {startDate && endDate && ( 
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  ({calculateDaysFromDateRange()} days)
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Revenue Intelligence */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Revenue Intelligence
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <KPICard
            title="Daily Revenue"
            value={`GH₵ ${revenueAnalysis?.daily_revenue.toFixed(2) || '0.00'}`}
            icon={FiDollarSign}
            iconColor="text-green-600 dark:text-green-400"
            bgColor="bg-green-100 dark:bg-green-900/20"
            subtitle={`${revenueAnalysis?.daily_transactions || 0} transactions today`}
          />
          <KPICard
            title="Weekly Revenue"
            value={`GH₵ ${revenueAnalysis?.weekly_revenue.toFixed(2) || '0.00'}`}
            icon={FiTrendingUp}
            iconColor="text-blue-600 dark:text-blue-400"
            bgColor="bg-blue-100 dark:bg-blue-900/20"
            subtitle={`${revenueAnalysis?.weekly_transactions || 0} transactions this week`}
          />
          <KPICard
            title="Monthly Revenue"
            value={`GH₵ ${revenueAnalysis?.monthly_revenue.toFixed(2) || '0.00'}`}
            icon={FiTrendingUp}
            iconColor="text-purple-600 dark:text-purple-400"
            bgColor="bg-purple-100 dark:bg-purple-900/20"
            subtitle={`${revenueAnalysis?.monthly_transactions || 0} transactions this month`}
          />
        </div>
      </div>

      {/* Financial KPIs */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Financial KPIs ({getDateRangeLabel()})
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <KPICard
            title="Gross Profit"
            value={`GH₵ ${financialKPIs?.gross_profit.toFixed(2) || '0.00'}`}
            icon={FiDollarSign}
            iconColor="text-green-600 dark:text-green-400"
            bgColor="bg-green-100 dark:bg-green-900/20"
            subtitle={`${financialKPIs?.profit_margin.toFixed(1) || '0'}% margin`}
          />
          <KPICard
            title="Net Profit"
            value={`GH₵ ${financialKPIs?.net_profit.toFixed(2) || '0.00'}`}
            icon={FiTrendingUp}
            iconColor="text-blue-600 dark:text-blue-400"
            bgColor="bg-blue-100 dark:bg-blue-900/20"
            subtitle="After 15% overhead"
          />
          <KPICard
            title="Outstanding Credit"
            value={`GH₵ ${financialKPIs?.outstanding_credit.toFixed(2) || '0.00'}`}
            icon={FiCreditCard}
            iconColor="text-orange-600 dark:text-orange-400"
            bgColor="bg-orange-100 dark:bg-orange-900/20"
            subtitle={`${financialKPIs?.credit_sales_count || 0} credit sales`}
          />
          <KPICard
            title="Avg Basket Value"
            value={`GH₵ ${financialKPIs?.average_basket_value.toFixed(2) || '0.00'}`}
            icon={FiShoppingCart}
            iconColor="text-purple-600 dark:text-purple-400"
            bgColor="bg-purple-100 dark:bg-purple-900/20"
            subtitle={`${financialKPIs?.total_transactions || 0} transactions`}
          />
        </div>
      </div>

      {/* Inventory Alerts */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Inventory Alerts
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <KPICard
            title="Expiring Soon"
            value={`${kpis?.items_near_expiry || 0}`}
            icon={FiAlertCircle}
            iconColor="text-red-600 dark:text-red-400"
            bgColor="bg-red-100 dark:bg-red-900/20"
            subtitle="Within 30 days"
          />
          <KPICard
            title="Low Stock"
            value={`${kpis?.low_stock_items || 0}`}
            icon={FiPackage}
            iconColor="text-orange-600 dark:text-orange-400"
            bgColor="bg-orange-100 dark:bg-orange-900/20"
            subtitle="Need reordering"
          />
          <KPICard
            title="Overstock Items"
            value={`${overstockItems?.length || 0}`} 
            icon={FiPackage}
            iconColor="text-yellow-600 dark:text-yellow-400"
            bgColor="bg-yellow-100 dark:bg-yellow-900/20"
            subtitle="Above 3x reorder level"
          />
          <KPICard
            title="Slow Moving"
            value={`${slowMoving?.length || 0}`}
            icon={FiTrendingUp}
            iconColor="text-gray-600 dark:text-gray-400"
            bgColor="bg-gray-100 dark:bg-gray-800"
            subtitle={`Low sales in period`}
          />
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sales Trend */}
        <div className="card p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Sales Trend
            </h3>
            <div className="flex gap-2">
              <button
                onClick={() => setTrendDays(7)}
                className={`px-2 py-1 text-xs rounded ${
                  trendDays === 7
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                }`}
              >
                7D
              </button>
              <button
                onClick={() => setTrendDays(14)}
                className={`px-2 py-1 text-xs rounded ${
                  trendDays === 14
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                }`}
              >
                14D
              </button>
              <button
                onClick={() => setTrendDays(30)}
                className={`px-2 py-1 text-xs rounded ${
                  trendDays === 30
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                }`}
              >
                30D
              </button>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={salesTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" stroke="#9CA3AF" />
              <YAxis stroke="#9CA3AF" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: '0.5rem',
                }}
              />
              <Line
                type="monotone"
                dataKey="total_revenue"
                stroke="#4F46E5"
                strokeWidth={2}
                name="Revenue (GH₵)"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Top Selling Products */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            Top Selling Products ({getDateRangeLabel()})
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={fastMoving}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="product_name" stroke="#9CA3AF" />
              <YAxis stroke="#9CA3AF" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: '0.5rem',
                }}
              />
              <Bar dataKey="total_sold" fill="#4F46E5" name="Units Sold" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Profit by Category */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            Profit by Category ({getDateRangeLabel()})
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={profitByCategory.slice(0, 6)}
                dataKey="total_profit"
                nameKey="category_name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={(entry) => `${entry.category_name}: GH₵${entry.total_profit.toFixed(0)}`}
              >
                {profitByCategory.slice(0, 6).map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: '0.5rem',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Inventory Value */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            Inventory Overview
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Total Inventory Value</span>
              <span className="text-xl font-bold text-gray-900 dark:text-gray-100">
                GH₵ {kpis?.inventory_value.toFixed(2) || '0.00'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Active Products</span>
              <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {kpis?.total_products || 0}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Capital in Overstock</span>
              <span className="text-lg font-semibold text-orange-600 dark:text-orange-400">
                GH₵ {overstockItems.reduce((sum, item) => sum + item.capital_tied, 0).toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Value at Risk (Expiring)</span>
              <span className="text-lg font-semibold text-red-600 dark:text-red-400">
                GH₵ {expiringProducts.reduce((sum, item) => sum + item.value_at_risk, 0).toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Expiring Products Table */}
      <div className="card p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Expiring Products
          </h3>
          <div className="flex gap-2">
            <button
              onClick={() => setExpiryDays(30)}
              className={`px-3 py-1 text-sm rounded ${
                expiryDays === 30
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
            >
              30 Days
            </button>
            <button
              onClick={() => setExpiryDays(60)}
              className={`px-3 py-1 text-sm rounded ${
                expiryDays === 60
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
            >
              60 Days
            </button>
            <button
              onClick={() => setExpiryDays(90)}
              className={`px-3 py-1 text-sm rounded ${
                expiryDays === 90
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
            >
              90 Days
            </button>
          </div>
        </div>
        <div className="overflow-x-auto max-h-96 overflow-y-auto custom-scrollbar">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Batch</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expiry Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Days Left</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value at Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {expiringProducts.map((product) => (
                <tr key={`${product.product_id}-${product.batch_number}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 dark:text-gray-100">{product.product_name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {product.dosage_form} {product.strength && `• ${product.strength}`}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{product.batch_number}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{product.batch_quantity}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                    {new Date(product.expiry_date).toLocaleDateString('en-GB')}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        product.days_until_expiry <= 30
                          ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                          : product.days_until_expiry <= 60
                          ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/20 dark:text-orange-400'
                          : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400'
                      }`}
                    >
                      {product.days_until_expiry} days
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                    GH₵ {product.value_at_risk.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      

            {/* Low Stock Items Table */}
      <div className="card p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Low Stock Items
          </h3>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {lowStockItems.length} items need attention
          </span>
        </div>
        <div className="overflow-x-auto max-h-96 overflow-y-auto custom-scrollbar">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Current Stock</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Threshold</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Units Needed</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {lowStockItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                    All products are well stocked! 🎉
                  </td>
                </tr>
              ) : (
                lowStockItems.map((item) => (
                  <tr key={item.product_id}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 dark:text-gray-100">{item.product_name}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {item.dosage_form} {item.strength && `• ${item.strength}`}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{item.sku}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-medium ${
                          item.current_stock === 0
                            ? 'text-red-600 dark:text-red-400'
                            : 'text-gray-900 dark:text-gray-100'
                        }`}
                      >
                        {item.current_stock}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{item.low_stock_threshold}</td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-orange-600 dark:text-orange-400">
                        {item.units_needed}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 text-xs rounded-full ${
                          item.status === 'out_of_stock'
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                            : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400'
                        }`}
                      >
                        {item.status === 'out_of_stock' ? 'Out of Stock' : 'Low Stock'}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Slow Moving Products Table */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
          Slow Moving Products ({getDateRangeLabel()})
        </h3>
        <div className="overflow-x-auto max-h-80 overflow-y-auto custom-scrollbar">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Current Stock</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Units Sold</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {slowMoving.map((product) => (
                <tr key={product.product_id}>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                    {product.product_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{product.sku}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{product.current_stock}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{product.total_sold}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Overstock Items Table */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
          Overstock Items
        </h3>
        <div className="overflow-x-auto max-h-80 overflow-y-auto custom-scrollbar">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Current Stock</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reorder Level</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Excess</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Capital Tied</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {overstockItems.map((item) => (
                <tr key={item.product_id}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 dark:text-gray-100">{item.product_name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {item.dosage_form} {item.strength && `• ${item.strength}`}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{item.sku}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{item.total_stock}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{item.reorder_level}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-1 text-xs rounded-full bg-orange-100 text-orange-700 dark:bg-orange-900/20 dark:text-orange-400">
                      +{item.excess_stock}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                    GH₵ {item.capital_tied.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
          Quick Actions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => (window.location.href = '/pos')}
            className="btn-primary"
          >
            New Sale
          </button>
          <button
            onClick={() => (window.location.href = '/products')}
            className="btn-secondary"
          >
            Manage Products
          </button>
          <button
            onClick={() => (window.location.href = '/notifications')}
            className="btn-secondary"
          >
            View Alerts
          </button>
        </div>
      </div>
    </div>
  )
}

interface KPICardProps {
  title: string
  value: string
  icon: any
  iconColor: string
  bgColor: string
  subtitle?: string
}

function KPICard({
  title,
  value,
  icon: Icon,
  iconColor,
  bgColor,
  subtitle,
}: KPICardProps) {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
            {title}
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-2">
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
              {subtitle}
            </p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${bgColor}`}>
          <Icon className={`h-6 w-6 ${iconColor}`} />
        </div>
      </div>
    </div>
  )
}

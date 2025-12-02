import { useState, useEffect } from 'react'
import { api } from '../services/api'
import {
  FiDollarSign,
  FiTrendingUp,
  FiTrendingDown,
  FiPackage,
  FiAlertCircle,
  FiShoppingCart,
  FiCreditCard,
  FiCalendar,
  FiArrowUp,
  FiArrowDown,
  FiMinus,
} from 'react-icons/fi'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
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

export default function DashboardPage() {
  const [kpis, setKpis] = useState<KPIs | null>(null)
  const [salesTrend, setSalesTrend] = useState<any[]>([])
  const [fastMoving, setFastMoving] = useState<any[]>([])
  const [slowMoving, setSlowMoving] = useState<any[]>([])
  const [revenueAnalysis, setRevenueAnalysis] = useState<RevenueAnalysis | null>(null)
  const [financialKPIs, setFinancialKPIs] = useState<FinancialKPIs | null>(null)
  const [expiringProducts, setExpiringProducts] = useState<ExpiringProduct[]>([])
  const [lowStockItems, setLowStockItems] = useState<LowStockItem[]>([])
  const [profitByCategory, setProfitByCategory] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [analysisPeriod, setAnalysisPeriod] = useState(30)

  useEffect(() => {
    loadDashboardData()
  }, [analysisPeriod])

  const loadDashboardData = async () => {
    setIsLoading(true)
    try {
      const [
        kpisData,
        trendData,
        fastMovingData,
        slowMovingData,
        revenueData,
        financialData,
        expiringData,
        lowStockData,
        profitCategoryData,
      ] = await Promise.all([
        api.getDashboardKPIs(),
        api.getSalesTrend({ days: analysisPeriod }),
        api.getFastMovingProducts({ limit: 10, days: analysisPeriod }),
        api.getSlowMovingProducts({ limit: 5, days: analysisPeriod }),
        api.getRevenueAnalysis(),
        api.getFinancialKPIs({ days: analysisPeriod }),
        api.getExpiringProducts({ days: 30, limit: 10 }),
        api.getLowStockItems({ limit: 50 }),
        api.getProfitByCategory({ days: analysisPeriod }),
      ])

      setKpis(kpisData)
      setSalesTrend(trendData)
      setFastMoving(fastMovingData)
      setSlowMoving(slowMovingData)
      setRevenueAnalysis(revenueData)
      setFinancialKPIs(financialData)
      setExpiringProducts(expiringData)
      setLowStockItems(lowStockData)
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

  // Calculate growth percentages (mock - you'd fetch yesterday's data in production)
  const dailyGrowth = 12.5 // Replace with actual calculation
  const profitGrowth = 8.3
  const basketGrowth = -2.1
  const transactionGrowth = 15.7

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Business Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Real-time insights and analytics for data-driven decisions
          </p>
        </div>

        {/* Period Filter */}
        <div className="flex items-center gap-2">
          <FiCalendar className="text-gray-500 dark:text-gray-400" />
          <div className="flex gap-2">
            {[7, 30, 90].map((days) => (
              <button
                key={days}
                onClick={() => setAnalysisPeriod(days)}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  analysisPeriod === days
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                {days}D
              </button>
            ))}
          </div>
        </div>
      </div>


      {/* Period Summary KPIs - Goes BEFORE Daily Revenue section */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Period Summary ({analysisPeriod} Days)
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <EnhancedKPICard
            title="Total Revenue"
            value={`GH₵ ${financialKPIs?.total_revenue.toFixed(2) || '0.00'}`}
            growth={12.5}
            subtitle={`${financialKPIs?.total_transactions || 0} transactions`}
            icon={FiDollarSign}
            iconColor="text-blue-600 dark:text-blue-400"
            bgColor="bg-blue-100 dark:bg-blue-900/20"
          />
          <EnhancedKPICard
            title="Total Items Sold"
            value={`${salesTrend.reduce((sum, day) => sum + (day.sales_count || 0), 0)}`}
            growth={8.3}
            subtitle="Units sold"
            icon={FiShoppingCart}
            iconColor="text-purple-600 dark:text-purple-400"
            bgColor="bg-purple-100 dark:bg-purple-900/20"
          />
          <EnhancedKPICard
            title="Total Profit"
            value={`GH₵ ${financialKPIs?.gross_profit.toFixed(2) || '0.00'}`}
            growth={15.7}
            subtitle={`${financialKPIs?.profit_margin.toFixed(1) || '0'}% margin`}
            icon={FiTrendingUp}
            iconColor="text-green-600 dark:text-green-400"
            bgColor="bg-green-100 dark:bg-green-900/20"
          />
          <EnhancedKPICard
            title="Avg Basket Value"
            value={`GH₵ ${financialKPIs?.average_basket_value.toFixed(2) || '0.00'}`}
            growth={-2.1}
            subtitle="Per transaction"
            icon={FiCreditCard}
            iconColor="text-orange-600 dark:text-orange-400"
            bgColor="bg-orange-100 dark:bg-orange-900/20"
          />
        </div>
      </div>

      {/* Enhanced KPIs with Growth Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <EnhancedKPICard
          title="Daily Revenue"
          value={`GH₵ ${revenueAnalysis?.daily_revenue.toFixed(2) || '0.00'}`}
          growth={dailyGrowth}
          subtitle={`${revenueAnalysis?.daily_transactions || 0} sales today`}
          icon={FiDollarSign}
          iconColor="text-green-600 dark:text-green-400"
          bgColor="bg-green-100 dark:bg-green-900/20"
        />
        <EnhancedKPICard
          title="Gross Profit"
          value={`GH₵ ${financialKPIs?.gross_profit.toFixed(2) || '0.00'}`}
          growth={profitGrowth}
          subtitle={`${financialKPIs?.profit_margin.toFixed(1) || '0'}% margin`}
          icon={FiTrendingUp}
          iconColor="text-blue-600 dark:text-blue-400"
          bgColor="bg-blue-100 dark:bg-blue-900/20"
        />
        <EnhancedKPICard
          title="Avg Basket Value"
          value={`GH₵ ${financialKPIs?.average_basket_value.toFixed(2) || '0.00'}`}
          growth={basketGrowth}
          subtitle={`${financialKPIs?.total_transactions || 0} transactions`}
          icon={FiShoppingCart}
          iconColor="text-purple-600 dark:text-purple-400"
          bgColor="bg-purple-100 dark:bg-purple-900/20"
        />
        <EnhancedKPICard
          title="Transaction Count"
          value={`${financialKPIs?.total_transactions || 0}`}
          growth={transactionGrowth}
          subtitle="Total transactions"
          icon={FiCreditCard}
          iconColor="text-orange-600 dark:text-orange-400"
          bgColor="bg-orange-100 dark:bg-orange-900/20"
        />
      </div>

      {/* Critical Alerts Banner */}
      {(lowStockItems.length > 0 || expiringProducts.length > 0) && (
        <div className="card p-4 bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800">
          <div className="flex items-start gap-3">
            <FiAlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-900 dark:text-red-100 mb-1">
                Critical Inventory Alerts
              </h3>
              <div className="text-sm text-red-700 dark:text-red-300 space-y-1">
                {lowStockItems.filter(i => i.status === 'out_of_stock').length > 0 && (
                  <p>• {lowStockItems.filter(i => i.status === 'out_of_stock').length} products out of stock</p>
                )}
                {lowStockItems.filter(i => i.status === 'low_stock').length > 0 && (
                  <p>• {lowStockItems.filter(i => i.status === 'low_stock').length} products below reorder level</p>
                )}
                {expiringProducts.filter(p => p.days_until_expiry <= 30).length > 0 && (
                  <p>• {expiringProducts.filter(p => p.days_until_expiry <= 30).length} products expiring within 30 days (Value: GH₵ {expiringProducts.filter(p => p.days_until_expiry <= 30).reduce((sum, p) => sum + p.value_at_risk, 0).toFixed(2)})</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

          {/* FULL WIDTH: Sales Trend - Dual Axis (Revenue + Transactions) */}
    <div className="card p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Daily Sales Performance
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Revenue and transaction trends over time
          </p>
        </div>
        <div className="flex gap-3">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-600 rounded"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">Revenue (GH₵)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-emerald-500 rounded"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">Transactions</span>
          </div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={salesTrend}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis 
            dataKey="date" 
            stroke="#9CA3AF"
            tick={{ fontSize: 11 }}
            tickFormatter={(date) => {
              const d = new Date(date);
              return `${d.getDate()}/${d.getMonth() + 1}`;
            }}
          />
          <YAxis 
            yAxisId="left"
            stroke="#3B82F6"
            tick={{ fontSize: 11 }}
            width={70}
            label={{ 
              value: 'Revenue (GH₵)', 
              angle: -90, 
              position: 'insideLeft',
              style: { fill: '#3B82F6', fontSize: 12 }
            }}
          />
          <YAxis 
            yAxisId="right"
            orientation="right"
            stroke="#10B981"
            tick={{ fontSize: 11 }}
            width={60}
            label={{ 
              value: 'Transactions', 
              angle: 90, 
              position: 'insideRight',
              style: { fill: '#10B981', fontSize: 12 }
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1F2937',
              border: '1px solid #374151',
              borderRadius: '0.5rem',
            }}
            labelFormatter={(date) => {
              const d = new Date(date);
              return d.toLocaleDateString('en-GB', { 
                weekday: 'short', 
                day: '2-digit', 
                month: 'short',
                year: 'numeric'
              });
            }}
            formatter={(value: any, name: string) => {
              if (name === 'Revenue (GH₵)') return [`GH₵ ${Number(value).toFixed(2)}`, 'Revenue'];
              if (name === 'Transactions') return [`${value} sales`, 'Transactions'];
              return [value, name];
            }}
          />
          <Legend 
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="total_revenue"
            stroke="#3B82F6"
            strokeWidth={3}
            name="Revenue (GH₵)"
            dot={{ fill: '#3B82F6', r: 6, strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 8 }}
            connectNulls
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="sales_count"
            stroke="#10B981"
            strokeWidth={3}
            name="Transactions"
            dot={{ fill: '#10B981', r: 6, strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 8 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
      
      {/* Quick Stats Below Chart
      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
        {salesTrend.length > 0 && (
          <>
            <div className="text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">Total Revenue</p>
              <p className="text-lg font-bold text-blue-600 dark:text-blue-400 mt-1">
                GH₵ {salesTrend.reduce((sum, day) => sum + (day.total_revenue || 0), 0).toFixed(2)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">Total Transactions</p>
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {salesTrend.reduce((sum, day) => sum + (day.sales_count || 0), 0)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">Avg Per Day</p>
              <p className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-1">
                GH₵ {(salesTrend.reduce((sum, day) => sum + (day.total_revenue || 0), 0) / salesTrend.length).toFixed(2)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">Avg Basket</p>
              <p className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-1">
                GH₵ {(
                  salesTrend.reduce((sum, day) => sum + (day.total_revenue || 0), 0) / 
                  salesTrend.reduce((sum, day) => sum + (day.sales_count || 0), 0)
                ).toFixed(2)}
              </p>
            </div>
          </>
        )}
      </div> */}
    </div>

      {/* FULL WIDTH: Top Products - Revenue + Quantity */}
      <div className="card p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Top Performing Products
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Best sellers by revenue and volume (Last {analysisPeriod} days)
          </p>
        </div>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={fastMoving} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis type="number" stroke="#9CA3AF" />
            <YAxis 
              type="category" 
              dataKey="product_name" 
              stroke="#9CA3AF"
              width={150}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
              }}
            />
            <Legend />
            <Bar dataKey="total_revenue" fill="#3B82F6" name="Revenue (GH₵)" />
            <Bar dataKey="total_sold" fill="#EAB308" name="Units Sold" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Business Insights - Two Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profit by Category */}
        <div className="card p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Category Performance
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Profit contribution by category
            </p>
          </div>
          <div className="space-y-3">
            {profitByCategory.slice(0, 6).map((cat, index) => (
              <div key={cat.category_id} className="flex items-center gap-3">
                <div 
                  className="w-10 h-10 rounded flex items-center justify-center text-white font-bold text-sm"
                  style={{ backgroundColor: ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'][index] }}
                >
                  {index + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-baseline">
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {cat.category_name}
                    </span>
                    <span className="text-sm font-bold text-gray-900 dark:text-gray-100 ml-2">
                      GH₵ {cat.total_profit.toFixed(0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden mr-2">
                      <div 
                        className="h-full bg-primary-600"
                        style={{ width: `${(cat.total_profit / profitByCategory[0].total_profit) * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {cat.profit_margin.toFixed(1)}% margin
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Inventory Health */}
        <div className="card p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Inventory Health
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Capital allocation and risk assessment
            </p>
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Total Inventory Value</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                  GH₵ {kpis?.inventory_value.toFixed(2) || '0.00'}
                </p>
              </div>
              <FiPackage className="h-8 w-8 text-gray-400" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <p className="text-xs text-green-700 dark:text-green-400">Active Products</p>
                <p className="text-xl font-bold text-green-900 dark:text-green-100 mt-1">
                  {kpis?.total_products || 0}
                </p>
              </div>
              <div className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                <p className="text-xs text-orange-700 dark:text-orange-400">Overstock Capital</p>
                <p className="text-xl font-bold text-orange-900 dark:text-orange-100 mt-1">
                  GH₵ {(kpis?.inventory_value * 0.15 || 0).toFixed(0)}
                </p>
              </div>
            </div>

            <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-xs text-red-700 dark:text-red-400">At-Risk Value (Expiring)</p>
                  <p className="text-xl font-bold text-red-900 dark:text-red-100 mt-1">
                    GH₵ {expiringProducts.reduce((sum, item) => sum + item.value_at_risk, 0).toFixed(2)}
                  </p>
                </div>
                <FiAlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
              </div>
              <p className="text-xs text-red-600 dark:text-red-400 mt-2">
                {expiringProducts.length} products need immediate action
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Critical Items Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Expiring Soon */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Expiring Soon (≤30 days)
          </h3>
          <div className="space-y-2 max-h-80 overflow-y-auto custom-scrollbar">
            {expiringProducts.filter(p => p.days_until_expiry <= 30).slice(0, 5).map((product) => (
              <div key={`${product.product_id}-${product.batch_number}`} 
                className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <p className="font-medium text-sm text-gray-900 dark:text-gray-100">
                      {product.product_name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Batch: {product.batch_number} • Qty: {product.batch_quantity}
                    </p>
                  </div>
                  <div className="text-right ml-3">
                    <span className="inline-block px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400">
                      {product.days_until_expiry}d
                    </span>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                      GH₵ {product.value_at_risk.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Low Stock */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Low Stock Alerts
          </h3>
          <div className="space-y-2 max-h-80 overflow-y-auto custom-scrollbar">
            {lowStockItems.slice(0, 5).map((item) => (
              <div key={item.product_id} 
                className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <p className="font-medium text-sm text-gray-900 dark:text-gray-100">
                      {item.product_name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Stock: {item.current_stock} / Threshold: {item.low_stock_threshold}
                    </p>
                  </div>
                  <div className="text-right ml-3">
                    <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${
                      item.status === 'out_of_stock'
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                        : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400'
                    }`}>
                      {item.status === 'out_of_stock' ? 'Out' : 'Low'}
                    </span>
                    <p className="text-xs text-orange-600 dark:text-orange-400 mt-1 font-medium">
                      Need: {item.units_needed}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
          Quick Actions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <button onClick={() => (window.location.href = '/pos')} className="btn-primary">
            <FiShoppingCart className="inline mr-2" />
            New Sale
          </button>
          <button onClick={() => (window.location.href = '/products')} className="btn-secondary">
            <FiPackage className="inline mr-2" />
            Manage Products
          </button>
          <button onClick={() => (window.location.href = '/notifications')} className="btn-secondary">
            <FiAlertCircle className="inline mr-2" />
            View Alerts ({kpis?.items_near_expiry || 0})
          </button>
          <button onClick={() => loadDashboardData()} className="btn-secondary">
            Refresh Data
          </button>
        </div>
      </div>
    </div>
  )
}

// Enhanced KPI Card with Growth Indicator
interface EnhancedKPICardProps {
  title: string
  value: string
  growth: number
  subtitle: string
  icon: any
  iconColor: string
  bgColor: string
}

function EnhancedKPICard({
  title,
  value,
  growth,
  subtitle,
  icon: Icon,
  iconColor,
  bgColor,
}: EnhancedKPICardProps) {
  const isPositive = growth > 0
  const isNeutral = growth === 0
  const GrowthIcon = isNeutral ? FiMinus : isPositive ? FiArrowUp : FiArrowDown

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-3">
        <div className={`p-3 rounded-lg ${bgColor}`}>
          <Icon className={`h-6 w-6 ${iconColor}`} />
        </div>
        <div className={`flex items-center gap-1 text-sm font-medium ${
          isNeutral ? 'text-gray-500' : isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
        }`}>
          <GrowthIcon className="h-4 w-4" />
          <span>{Math.abs(growth).toFixed(1)}%</span>
        </div>
      </div>
      <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
        {title}
      </p>
      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-2">
        {value}
      </p>
      <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
        {subtitle}
      </p>
    </div>
  )
}
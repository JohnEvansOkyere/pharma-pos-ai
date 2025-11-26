import { useState, useEffect } from 'react'
import { api } from '../services/api'
import {
  FiDollarSign,
  FiTrendingUp,
  FiPackage,
  FiAlertCircle,
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

export default function DashboardPage() {
  const [kpis, setKpis] = useState<KPIs | null>(null)
  const [salesTrend, setSalesTrend] = useState<any[]>([])
  const [fastMoving, setFastMoving] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    setIsLoading(true)
    try {
      const [kpisData, trendData, fastMovingData] = await Promise.all([
        api.getDashboardKPIs(),
        api.getSalesTrend({ days: 7 }),
        api.getFastMovingProducts({ limit: 5, days: 30 }),
      ])

      setKpis(kpisData)
      setSalesTrend(trendData)
      setFastMoving(fastMovingData)
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

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Dashboard
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Overview of your pharmacy operations
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          title="Sales Today"
          value={`$${kpis?.total_sales_today.toFixed(2) || '0.00'}`}
          icon={FiDollarSign}
          iconColor="text-green-600"
          bgColor="bg-green-100 dark:bg-green-900/20"
          subtitle={`${kpis?.total_sales_count || 0} transactions`}
        />

        <KPICard
          title="Profit Today"
          value={`$${kpis?.profit_today.toFixed(2) || '0.00'}`}
          icon={FiTrendingUp}
          iconColor="text-blue-600"
          bgColor="bg-blue-100 dark:bg-blue-900/20"
        />

        <KPICard
          title="Inventory Value"
          value={`$${kpis?.inventory_value.toFixed(2) || '0.00'}`}
          icon={FiPackage}
          iconColor="text-purple-600"
          bgColor="bg-purple-100 dark:bg-purple-900/20"
          subtitle={`${kpis?.total_products || 0} products`}
        />

        <KPICard
          title="Alerts"
          value={`${
            (kpis?.items_near_expiry || 0) + (kpis?.low_stock_items || 0)
          }`}
          icon={FiAlertCircle}
          iconColor="text-red-600"
          bgColor="bg-red-100 dark:bg-red-900/20"
          subtitle={`${kpis?.low_stock_items || 0} low stock, ${
            kpis?.items_near_expiry || 0
          } expiring`}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sales Trend */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            Sales Trend (7 Days)
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={salesTrend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="total_revenue"
                stroke="#4F46E5"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Fast Moving Products */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            Top Selling Products (30 Days)
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={fastMoving}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="product_name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="total_sold" fill="#4F46E5" />
            </BarChart>
          </ResponsiveContainer>
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

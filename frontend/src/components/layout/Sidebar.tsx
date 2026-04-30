import { NavLink } from 'react-router-dom'
import {
  FiChevronLeft,
  FiClipboard,
  FiCloud,
  FiHome,
  FiPackage,
  FiShoppingCart,
  FiDollarSign,
  FiRefreshCw,
  FiUsers,
  FiBell,
  FiSettings,
} from 'react-icons/fi'
import { useAuthStore } from '../../stores/authStore'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: FiHome, adminOnly: true },
  { name: 'Cloud Dashboard', href: '/cloud-dashboard', icon: FiCloud, adminOrManager: true },
  { name: 'Audit Logs', href: '/audit-logs', icon: FiClipboard, adminOnly: true },
  { name: 'Products', href: '/products', icon: FiPackage },
  { name: 'POS', href: '/pos', icon: FiShoppingCart },
  { name: 'Sales', href: '/sales', icon: FiDollarSign },
  { name: 'Stock Adjustments', href: '/stock-adjustments', icon: FiRefreshCw, adminOrManager: true },
  { name: 'Suppliers', href: '/suppliers', icon: FiUsers },
  { name: 'Notifications', href: '/notifications', icon: FiBell },
  { name: 'Settings', href: '/settings', icon: FiSettings, adminOrManager: true },
]

interface SidebarProps {
  onHide: () => void
}

export default function Sidebar({ onHide }: SidebarProps) {
  const { user } = useAuthStore()
  return (
    <div className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Logo */}
      <div className="h-16 flex items-center justify-between gap-3 px-4 border-b border-gray-200 dark:border-gray-700">
        <h1 className="min-w-0 truncate text-lg font-bold text-primary-600 dark:text-primary-400">
          GYSBIN PHARMACY-ANNEX
        </h1>
        <button
          onClick={onHide}
          className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200"
          aria-label="Hide sidebar"
          title="Hide sidebar"
        >
          <FiChevronLeft className="h-5 w-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto custom-scrollbar">
        {navigation
          .filter((item) => {
            if (item.adminOnly) return user?.role === 'admin'
            if (item.adminOrManager) return user?.role === 'admin' || user?.role === 'manager'
            return true
          })
          .map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                `flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                  isActive
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/20 dark:text-primary-400'
                    : 'text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    className={`mr-3 h-5 w-5 ${
                      isActive ? 'text-primary-600 dark:text-primary-400' : ''
                    }`}
                  />
                  {item.name}
                </>
              )}
            </NavLink>
          ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
          v1.0.0 • Local Backend Required
        </p>
      </div>
    </div>
  )
}

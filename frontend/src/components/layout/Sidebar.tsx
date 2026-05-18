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
  FiServer,
} from 'react-icons/fi'
import { useAuthStore } from '../../stores/authStore'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: FiHome, group: 'OVERVIEW', adminOnly: true },
  { name: 'Cloud Dashboard', href: '/cloud-dashboard', icon: FiCloud, group: 'OVERVIEW', adminOrManager: true },
  { name: 'Audit Logs', href: '/audit-logs', icon: FiClipboard, group: 'OVERVIEW', adminOnly: true },
  { name: 'Products', href: '/products', icon: FiPackage, group: 'PHARMACY' },
  { name: 'POS', href: '/pos', icon: FiShoppingCart, group: 'PHARMACY' },
  { name: 'Sales', href: '/sales', icon: FiDollarSign, group: 'PHARMACY' },
  { name: 'Stock Adjustments', href: '/stock-adjustments', icon: FiRefreshCw, group: 'PHARMACY', adminOrManager: true },
  { name: 'Suppliers', href: '/suppliers', icon: FiUsers, group: 'PHARMACY' },
  { name: 'Notifications', href: '/notifications', icon: FiBell, group: 'SYSTEM' },
  { name: 'Settings', href: '/settings', icon: FiSettings, group: 'SYSTEM', adminOrManager: true },
  { name: 'Clients', href: '/clients', icon: FiServer, group: 'SYSTEM', adminOnly: true },
]

const SIDEBAR_BG = '#1e3050'

interface SidebarProps {
  onHide: () => void
}

export default function Sidebar({ onHide }: SidebarProps) {
  const { user } = useAuthStore()
  return (
    <div className="w-56 flex flex-col flex-shrink-0" style={{ backgroundColor: SIDEBAR_BG }}>
      {/* Logo */}
      <div
        className="h-12 flex items-center justify-between gap-2 px-3"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}
      >
        <h1 className="min-w-0 truncate text-sm font-semibold tracking-wide text-white">
          GYSBIN PHARMACY
        </h1>
        <button
          onClick={onHide}
          className="flex-shrink-0 rounded p-1 transition-colors hover:bg-white/10"
          style={{ color: 'rgba(255,255,255,0.4)' }}
          aria-label="Hide sidebar"
          title="Hide sidebar"
        >
          <FiChevronLeft className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        {(['OVERVIEW', 'PHARMACY', 'SYSTEM'] as const).map((group) => {
          const items = navigation.filter((item) => {
            if (item.group !== group) return false
            if (item.adminOnly) return user?.role === 'admin'
            if (item.adminOrManager) return user?.role === 'admin' || user?.role === 'manager'
            return true
          })
          if (items.length === 0) return null
          return (
            <div key={group} className="mb-4">
              <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest"
                style={{ color: 'rgba(255,255,255,0.35)' }}>
                {group}
              </p>
              <div className="space-y-0.5">
                {items.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    className={({ isActive }) =>
                      `flex items-center px-3 py-2 font-normal rounded transition-colors ${
                        isActive ? 'text-white' : 'hover:text-white hover:bg-white/5'
                      }`
                    }
                    style={({ isActive }) => ({
                      fontSize: '14px',
                      backgroundColor: isActive ? 'rgba(255,255,255,0.12)' : undefined,
                      color: isActive ? '#fff' : 'rgba(255,255,255,0.82)',
                    })}
                  >
                    {({ isActive }) => (
                      <>
                        <item.icon
                          className="mr-3 h-4 w-4 flex-shrink-0"
                          style={{ color: isActive ? '#fff' : 'rgba(255,255,255,0.55)' }}
                        />
                        {item.name}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-2.5" style={{ borderTop: '1px solid rgba(255,255,255,0.07)' }}>
        <p className="text-center" style={{ fontSize: '10px', color: 'rgba(255,255,255,0.25)' }}>
          v1.0.0 · Local
        </p>
      </div>
    </div>
  )
}

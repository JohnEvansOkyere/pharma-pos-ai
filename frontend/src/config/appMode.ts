export const APP_MODE = (import.meta.env.VITE_APP_MODE || 'local_pos').trim().toLowerCase()

export const isCloudReportingMode = APP_MODE === 'cloud_reporting'
export const isOnlinePosMode = APP_MODE === 'online_pos'
export const isLocalPosMode = APP_MODE === 'local_pos'

/**
 * True when POS write operations are available (local_pos or online_pos).
 * In cloud_reporting mode, POS is disabled.
 */
export const isPosMode = isLocalPosMode || isOnlinePosMode

export function getDefaultAuthenticatedPath(user?: { role?: string; organization_id?: number | null } | null) {
  if (isCloudReportingMode) {
    if (user?.role === 'admin' && !user.organization_id) return '/clients'
    if (user?.role === 'admin' || user?.role === 'manager') return '/cloud-dashboard'
    return '/login'
  }

  // online_pos mode: admin/manager default to cloud-dashboard, cashier to POS
  if (isOnlinePosMode) {
    if (user?.role === 'admin' || user?.role === 'manager') return '/cloud-dashboard'
    return '/pos'
  }

  // local_pos mode
  return user?.role === 'admin' ? '/dashboard' : '/pos'
}
